from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..services.resume_parser import extract_text_from_pdf, extract_keywords
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
        if 'resume' not in request.files:
            return jsonify({'error': 'no file'}), 400
        file = request.files['resume']
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        text = extract_text_from_pdf(path)
        keywords = extract_keywords(text)
        users.update_one({'email': current_user.email}, {'$set': {'keywords': keywords}})
        return jsonify({'status': 'ok', 'keywords': keywords})
    return render_template('upload.html')
