from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from ..services.gemini_service import generate_questions, evaluate_answer
from ..services.vapi_service import tts_synthesize, stt_transcribe
from pymongo import MongoClient
import os

interview_bp = Blueprint('interview', __name__)

# TODO: share DB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')
client = MongoClient(MONGO_URI)
db = client.get_default_database() if client else client['interview_app']
users = db.users


@interview_bp.route('/interview')
@login_required
def interview_page():
    user_doc = users.find_one({'email': current_user.email})
    return render_template('interview.html', user=user_doc)


@interview_bp.route('/api/get_question')
@login_required
def api_get_question():
    user_doc = users.find_one({'email': current_user.email})
    keywords = user_doc.get('keywords', [])
    q = generate_questions(keywords, count=7)
    # return one question at a time; here we return the full list and the client handles ordering
    return jsonify({'questions': q})


@interview_bp.route('/get_questions')
@login_required
def get_questions():
    """Return generated questions based on skills stored in session or DB.
    This endpoint is intended for the interview frontend to fetch questions
    after a resume upload.
    """
    # Prefer session-stored skills (set by /upload_resume)
    skills = []
    try:
        from flask import session
        skills = session.get('skills', []) or []
    except Exception:
        skills = []

    # Fallback to DB-stored keywords
    if not skills:
        user_doc = users.find_one({'email': current_user.email})
        skills = user_doc.get('keywords', []) if user_doc else []

    try:
        questions = generate_questions(skills, count=7)
    except Exception:
        current_app.logger.exception('Failed to generate questions')
        questions = []

    return jsonify({'questions': questions, 'skills': skills})


@interview_bp.route('/api/tts', methods=['POST'])
@login_required
def api_tts():
    data = request.json
    text = data.get('text', '')
    # TTS service returns URL or bytes; here we return a placeholder
    audio_url = tts_synthesize(text)
    return jsonify({'audio_url': audio_url})


@interview_bp.route('/api/stt', methods=['POST'])
@login_required
def api_stt():
    # Expect audio blob uploaded as form-data file 'audio'
    if 'audio' not in request.files:
        return jsonify({'error': 'no audio'}), 400
    audio = request.files['audio']
    transcript = stt_transcribe(audio)
    return jsonify({'transcript': transcript})


@interview_bp.route('/api/evaluate', methods=['POST'])
@login_required
def api_evaluate():
    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    result = evaluate_answer(question, answer)
    # store result in user history
    users.update_one({'email': current_user.email}, {'$push': {'results': {'question': question, 'answer': answer, 'result': result}}})
    return jsonify({'result': result})


@interview_bp.route('/results')
@login_required
def results_page():
    user_doc = users.find_one({'email': current_user.email})
    results = user_doc.get('results', [])
    return render_template('result.html', results=results)
