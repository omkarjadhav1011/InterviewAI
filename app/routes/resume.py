from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..services.resume_parser import extract_text_from_pdf, extract_keywords, extract_skills, parse_resume_to_skills
from ..services.gemini_service import generate_questions
from ..extensions import get_db

resume_bp = Blueprint('resume', __name__)


@resume_bp.route('/')
@login_required
def home():
    users = get_db().users
    user_doc = users.find_one({'email': current_user.email})
    return render_template('home.html', user=user_doc)


@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        users = get_db().users

        # Basic checks
        if 'resume' not in request.files:
            return jsonify({'status': 'error', 'error': 'no file provided'}), 400
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'empty filename'}), 400

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
                return jsonify({'status': 'error', 'error': 'server upload folder error'}), 500

        path = os.path.join(upload_folder, filename)

        # Only accept PDFs (basic check)
        if not (filename.lower().endswith('.pdf') or file.mimetype == 'application/pdf'):
            return jsonify({'status': 'error', 'error': 'only PDF files are accepted'}), 400

        try:
            file.save(path)
            current_app.logger.info('Resume saved to: %s', path)
        except Exception:
            current_app.logger.exception('Failed to save uploaded file')
            return jsonify({'status': 'error', 'error': 'could not save file'}), 500

        # Parse the saved PDF and extract data
        try:
            skills = parse_resume_to_skills(path)
            current_app.logger.info('Extracted %d skills from resume', len(skills))

            try:
                users.update_one(
                    {'email': current_user.email},
                    {'$set': {'skills': skills}}
                )
                session['skills'] = skills
                current_app.logger.info('Resume skills stored in session and DB')
            except Exception:
                current_app.logger.exception('Failed to update user skills in DB')

            # Generate initial questions
            questions = []
            try:
                questions = generate_questions(skills, count=5)
                session['interview_questions'] = questions
                current_app.logger.info('Generated %d questions from skills', len(questions))
            except Exception:
                current_app.logger.exception('Failed to generate questions')

            return jsonify({
                'status': 'ok',
                'skills': skills,
                'questions': questions,
                'next': url_for('interview.interview_page')
            })
        except Exception:
            current_app.logger.exception('Error parsing resume')
            return jsonify({'status': 'error', 'error': 'failed to parse resume'}), 500
    return render_template('upload.html')
