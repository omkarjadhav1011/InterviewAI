from flask import Blueprint, render_template, request, jsonify, current_app, session, url_for
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
    """Return interview questions and skills, with the following priority:
    1. Questions stored in session (from resume upload)
    2. Generate new questions from session skills
    3. Generate questions from DB skills
    4. Return empty lists if no data available
    """
    # Get the requested question number (0-based index)
    question_number = request.args.get('question', type=int, default=0)
    
    # First try to get pre-generated questions from session
    questions = session.get('interview_questions', [])
    current_app.logger.debug('Session questions: %s', len(questions) if questions else 0)
    
    # Get skills with fallback chain: session -> DB -> empty
    skills = session.get('skills', [])
    if not skills:
        user_doc = users.find_one({'email': current_user.email})
        if user_doc:
            skills = user_doc.get('skills', [])
    current_app.logger.debug('Available skills: %s', len(skills) if skills else 0)

    # If we have skills but no questions, generate them
    if skills and not questions:
        try:
            questions = generate_questions(skills, count=5)  # Generate exactly 5 questions
            # Store in session for consistency
            session['interview_questions'] = questions
            current_app.logger.info('Generated %d new questions', len(questions))
            print(f'Generated {len(questions)} questions')
        except Exception:
            current_app.logger.exception('Failed to generate questions from skills')
            questions = []
    
    # Return the current question number and total, plus the current question
    current_question = questions[question_number] if questions and question_number < len(questions) else None
    
    return jsonify({
        'currentQuestion': current_question,
        'questionNumber': question_number,
        'totalQuestions': len(questions),
        'progress': {
            'current': question_number + 1,
            'total': 5,
            'completed': question_number / 5 * 100
        },
        'skills': skills,
        'isLastQuestion': question_number >= 4  # 0-based index, so 4 is the 5th question
    })


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
    question_number = data.get('questionNumber', 0)
    
    # Get evaluation from Gemini
    result = evaluate_answer(question, answer)
    
    # Store in session to track progress
    session_results = session.get('interview_results', [])
    session_results.append({
        'question': question,
        'answer': answer,
        'result': result,
        'questionNumber': question_number
    })
    session['interview_results'] = session_results
    
    # If this was the last question (5th), store all results in DB
    if question_number >= 4:  # 0-based index, so 4 is the 5th question
        users.update_one(
            {'email': current_user.email},
            {
                '$push': {
                    'results': {
                        '$each': session_results
                    }
                }
            }
        )
        # Clear session results after storing
        session.pop('interview_results', None)
        result['redirect'] = url_for('interview.results_page')
    
    return jsonify({'result': result, 'questionNumber': question_number})


@interview_bp.route('/results')
@login_required
def results_page():
    user_doc = users.find_one({'email': current_user.email})
    results = user_doc.get('results', [])
    return render_template('result.html', results=results)
