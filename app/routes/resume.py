from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..services.resume_parser import extract_text_from_pdf, extract_keywords, extract_skills
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
        except Exception as e:
            current_app.logger.exception('Failed to save uploaded file')
            return jsonify({'error': 'could not save file'}), 500

        # Parse the saved PDF and extract data. Wrap in try/except to return friendly errors.
        try:
            text = extract_text_from_pdf(path)
            skills = extract_skills(text)  # from skill DB
            keywords = extract_keywords(text)  # broader keywords

            # Persist keywords to user's record (non-blocking in terms of response formatting)
            try:
                users.update_one({'email': current_user.email}, {'$set': {'keywords': keywords}})
            except Exception:
                current_app.logger.exception('Failed to update user keywords in DB')

            # Return both keys so frontend can choose
            return jsonify({'status': 'ok', 'skills': skills, 'keywords': keywords})
        except Exception as e:
            current_app.logger.exception('Error parsing resume')
            return jsonify({'error': 'failed to parse resume'}), 500
    return render_template('upload.html')
