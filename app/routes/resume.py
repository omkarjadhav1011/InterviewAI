from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..services.resume_parser import extract_text_from_pdf, extract_keywords, extract_skills, parse_resume_to_skills
from ..services.gemini_service import generate_questions
from pymongo import MongoClient

resume_bp = Blueprint('resume', __name__)

# TODO: reuse shared DB client
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')
client = MongoClient(MONGO_URI)
db = client.get_default_database() if client else client['interview_app']
users = db.users


@resume_bp.route('/')
@login_required
def home():
    # Dashboard after login
    user_doc = users.find_one({'email': current_user.email})
    return render_template('home.html', user=user_doc)


@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # Basic checks
        if 'resume' not in request.files:
            return jsonify({'error': 'no file provided'}), 400
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'empty filename'}), 400

        filename = secure_filename(file.filename)

        # Ensure upload folder exists
        upload_folder = current_app.config.get('UPLOAD_FOLDER', None)
        if not upload_folder:
            # Fallback to a local uploads folder within the project
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.isdir(upload_folder):
            try:
                os.makedirs(upload_folder, exist_ok=True)
            except Exception as e:
                current_app.logger.exception('Could not create upload folder')
                return jsonify({'error': 'server upload folder error'}), 500

        path = os.path.join(upload_folder, filename)

        # Only accept PDFs (basic check)
        if not (filename.lower().endswith('.pdf') or file.mimetype == 'application/pdf'):
            return jsonify({'error': 'only PDF files are accepted'}), 400

        try:
            file.save(path)
            current_app.logger.info('Resume saved to: %s', path)
            print(f'Resume upload: saved to {path}')
        except Exception as e:
            current_app.logger.exception('Failed to save uploaded file')
            return jsonify({'error': 'could not save file'}), 500

        # Parse the saved PDF and extract data. Wrap in try/except to return friendly errors.
        try:
            # Extract skills using the combined helper that merges DB matches and keywords
            skills = parse_resume_to_skills(path)
            current_app.logger.info('Extracted %d skills from resume', len(skills))
            print(f'Resume parsing: found {len(skills)} skills')

            # Persist skills to user's record (non-blocking in terms of response formatting)
            try:
                users.update_one(
                    {'email': current_user.email}, 
                    {'$set': {'skills': skills}}
                )
                # Store in session for immediate use in interview
                session['skills'] = skills
                print('Resume skills: stored in session and DB')
            except Exception:
                current_app.logger.exception('Failed to update user skills in DB')

            # Generate initial questions
            questions = []
            try:
                questions = generate_questions(skills, count=5)
                session['interview_questions'] = questions
                print(f'Generated {len(questions)} questions from skills')
            except Exception:
                current_app.logger.exception('Failed to generate questions')

            return jsonify({
                'status': 'ok',
                'skills': skills,
                'questions': questions,
                'next': url_for('interview.interview_page')
            })
        except Exception as e:
            current_app.logger.exception('Error parsing resume')
            return jsonify({'error': 'failed to parse resume'}), 500
    return render_template('upload.html')



@resume_bp.route('/upload_resume', methods=['POST'])
@login_required
def upload_resume():
    """Accept a resume (PDF or DOCX), parse skills, optionally generate questions via Gemini,
    store skills in session and return JSON with skills and questions.
    """
    if 'resume' not in request.files:
        return jsonify({'error': 'no file provided'}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'empty filename'}), 400

    filename = secure_filename(file.filename)

    # Ensure upload folder exists
    upload_folder = current_app.config.get('UPLOAD_FOLDER', None)
    if not upload_folder:
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    if not os.path.isdir(upload_folder):
        try:
            os.makedirs(upload_folder, exist_ok=True)
        except Exception:
            current_app.logger.exception('Could not create upload folder')
            return jsonify({'error': 'server upload folder error'}), 500

    path = os.path.join(upload_folder, filename)

    # Accept PDF and DOCX
    allowed = ('.pdf', '.docx')
    if not filename.lower().endswith(allowed):
        return jsonify({'error': 'only PDF or DOCX files are accepted'}), 400

    try:
        file.save(path)
        # Debug/log: file saved successfully
        current_app.logger.info('Resume file saved: %s', path)
        print(f"Resume upload: saved file to {path}")
    except Exception:
        current_app.logger.exception('Failed to save uploaded file')
        print('Resume upload: failed to save file')
        return jsonify({'error': 'could not save file'}), 500

    try:
        # Parse resume and extract skills
        skills = parse_resume_to_skills(path)
        current_app.logger.info('Parsed resume and extracted %d skills (showing up to 10)', len(skills))
        print(f"Resume parsing: extracted {len(skills)} skills. Sample: {skills[:10]}")
        # Persist minimal skills into DB (non-blocking)
        try:
            users.update_one({'email': current_user.email}, {'$set': {'keywords': skills}})
        except Exception:
            current_app.logger.exception('Failed to update user keywords in DB')

        # Save skills to session for later retrieval on /get_questions
        session['skills'] = skills
        current_app.logger.info('Skills saved to session for user.')
        print('Resume upload: skills saved to session.')

        # Generate questions immediately (best-effort)
        questions = []
        try:
            questions = generate_questions(skills, count=7)
            current_app.logger.info('Generated %d questions for uploaded resume.', len(questions))
            print(f"Generated {len(questions)} questions from Gemini/fallback.")
        except Exception:
            current_app.logger.exception('Gemini question generation failed')
            print('Gemini question generation failed; returning skills without questions.')

        # Debug/log: returning skills and questions
        current_app.logger.debug('Returning skills and questions JSON to client')
        print('Resume upload: returning skills and questions to client.')

        return jsonify({'status': 'ok', 'skills': skills, 'questions': questions})
    except Exception:
        current_app.logger.exception('Error parsing resume')
        return jsonify({'error': 'failed to parse resume'}), 500
