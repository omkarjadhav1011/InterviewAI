from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, jsonify, session,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os

from ..services.resume_parser import (
    extract_text_from_pdf_bytes,
    extract_structured_profile,
    parse_resume_to_skills_from_text,
)
from ..services.gemini_service import generate_questions
from ..extensions import get_db

resume_bp = Blueprint('resume', __name__)


@resume_bp.route('/')
@login_required
def home():
    db = get_db()
    user_doc = db.users.find_one({'email': current_user.email}) or {}

    runs = list(
        db.interview_runs.find(
            {'user_email': current_user.email},
            {
                'created_at': 1,
                'final_scores': 1,
                'results': 1,
                'questions': 1,
                'skills': 1,
                'full_evaluation': 1,
            },
        ).sort('created_at', -1).limit(20)
    )

    latest_results = []
    for r in runs:
        fs = r.get('final_scores') or {}
        per_q = r.get('results') or []
        score = fs.get('overall_score')
        if score is None and per_q:
            scores = [
                p.get('overall_score') for p in per_q
                if isinstance(p.get('overall_score'), (int, float))
            ]
            score = round(sum(scores) / len(scores), 1) if scores else None

        rec = fs.get('hire_recommendation') or ''
        verdict_map = {
            'strong_yes': 'Strong Hire',
            'yes': 'Hire',
            'maybe': 'Weak Hire',
            'no': 'Reject',
        }
        verdict = verdict_map.get(rec, rec.replace('_', ' ').title() if rec else '')

        created = r.get('created_at')
        latest_results.append({
            'overall_score': score,
            'verdict': verdict,
            'created_at': created.isoformat() if created else None,
            'title': 'Mock Interview',
            'num_questions': len(r.get('questions') or []) or len(per_q),
        })

    user_doc['latest_results'] = latest_results
    return render_template('home.html', user=user_doc)


@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'GET':
        return render_template('upload.html')

    db = get_db()
    users = db.users

    # Basic checks
    if 'resume' not in request.files:
        return jsonify({'status': 'error', 'error': 'no file provided'}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'status': 'error', 'error': 'empty filename'}), 400

    filename = secure_filename(file.filename)
    if not (filename.lower().endswith('.pdf') or file.mimetype == 'application/pdf'):
        return jsonify({'status': 'error', 'error': 'only PDF files are accepted'}), 400

    # Read into memory once; enforce per-resume size cap
    try:
        file_bytes = file.read()
    except Exception:
        current_app.logger.exception('Failed to read uploaded file')
        return jsonify({'status': 'error', 'error': 'could not read uploaded file'}), 500

    max_bytes = current_app.config.get('MAX_RESUME_SIZE_BYTES', 5 * 1024 * 1024)
    if len(file_bytes) > max_bytes:
        return jsonify({
            'status': 'error',
            'error': f'resume exceeds {max_bytes // (1024 * 1024)}MB limit'
        }), 413

    # Persist a copy for audit/debug
    upload_folder = current_app.config.get('UPLOAD_FOLDER') or \
        os.path.join(current_app.root_path, 'static', 'uploads')
    try:
        os.makedirs(upload_folder, exist_ok=True)
        path = os.path.join(upload_folder, filename)
        with open(path, 'wb') as f:
            f.write(file_bytes)
        current_app.logger.info('Resume saved to: %s', path)
    except Exception:
        current_app.logger.exception('Could not persist resume to disk (continuing)')

    # Extract text with hardened bytes-based parser
    text, extract_err = extract_text_from_pdf_bytes(
        file_bytes,
        max_pages=current_app.config.get('MAX_RESUME_PAGES', 10),
        timeout_seconds=current_app.config.get('PDF_EXTRACTION_TIMEOUT', 20),
    )
    if extract_err and not text:
        current_app.logger.warning('Resume extraction failed: %s', extract_err)
        return jsonify({'status': 'error', 'error': extract_err}), 400

    # Structured profile (Gemini-backed, falls back to deterministic scorer internally)
    try:
        profile = extract_structured_profile(text)
    except Exception:
        current_app.logger.exception('extract_structured_profile crashed; using fallback')
        profile = {
            'skills': parse_resume_to_skills_from_text(text),
            'experience_years': None,
            'job_titles': [],
            'education': [],
            'name': None,
            'summary': '',
        }

    skills = profile.get('skills') or []
    if not skills:
        skills = parse_resume_to_skills_from_text(text)
        profile['skills'] = skills

    current_app.logger.info('Extracted %d skills from resume', len(skills))

    # Persist skills to users (legacy field, still read by /profile and /get_questions)
    try:
        users.update_one(
            {'email': current_user.email},
            {'$set': {'skills': skills}},
        )
        session['skills'] = skills
    except Exception:
        current_app.logger.exception('Failed to update user skills in DB')

    # Store the full structured profile in the session so question generation
    # can personalize on years/titles/education/summary, not just skills.
    session['candidate_profile'] = {
        'skills': skills,
        'name': profile.get('name'),
        'summary': profile.get('summary', ''),
        'experience_years': profile.get('experience_years'),
        'job_titles': profile.get('job_titles', []),
        'education': profile.get('education', []),
    }

    # Upsert into resumes collection (one doc per user)
    try:
        db.resumes.update_one(
            {'user_email': current_user.email},
            {'$set': {
                'user_email': current_user.email,
                'filename': filename,
                'parsed_at': datetime.now(timezone.utc),
                'skills': skills,
                'name': profile.get('name'),
                'summary': profile.get('summary', ''),
                'experience_years': profile.get('experience_years'),
                'job_titles': profile.get('job_titles', []),
                'education': profile.get('education', []),
            }},
            upsert=True,
        )
    except Exception:
        current_app.logger.exception('Failed to upsert resume document (non-fatal)')

    # Generate questions synchronously, passing the full profile so each
    # question is calibrated to the candidate's seniority, role, and skill mix
    # rather than being string-substituted from a single skill.
    import time as _time
    session_seed = int(_time.time() * 1000) & 0xFFFF
    session['interview_seed'] = session_seed
    try:
        questions = generate_questions(
            skills, count=5,
            profile=session['candidate_profile'],
            session_seed=session_seed,
        )
    except Exception:
        current_app.logger.exception('Question generation crashed; using profile-aware fallback')
        from ..services.gemini_service import _generate_skill_based_questions
        questions = _generate_skill_based_questions(
            skills, count=5, profile=session['candidate_profile'], seed=session_seed,
        )
    session['interview_questions'] = questions
    session['interview_results'] = []

    return jsonify({
        'status': 'ok',
        'skills': skills,
        'questions': questions,
        'next': url_for('interview.interview_page'),
        # Additive fields — interview.js / resume.js ignore unknown keys
        'name': profile.get('name'),
        'summary': profile.get('summary', ''),
        'experience_years': profile.get('experience_years'),
        'job_titles': profile.get('job_titles', []),
    })
