from flask import Blueprint, render_template, request, jsonify, current_app, session, url_for
from flask_login import login_required, current_user
from ..services.gemini_service import generate_questions, evaluate_answer, evaluate_full_interview
from ..services.vapi_service import tts_synthesize, stt_transcribe
from pymongo import MongoClient
import os
import datetime

interview_bp = Blueprint('interview', __name__)

# TODO: share DB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')
client = MongoClient(MONGO_URI)
db = client.get_default_database() if client else client['interview_app']
users = db.users
# New collection for storing interview runs as separate documents
interview_runs = db.interview_runs


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
    question_number = request.args.get('question', type=int, default=0)

    questions = session.get('interview_questions', [])
    current_app.logger.debug('Session questions: %s', len(questions) if questions else 0)

    skills = session.get('skills', [])
    if not skills:
        user_doc = users.find_one({'email': current_user.email})
        if user_doc:
            skills = user_doc.get('skills', [])
    current_app.logger.debug('Available skills: %s', len(skills) if skills else 0)

    if skills and not questions:
        try:
            questions = generate_questions(skills, count=5)
            session['interview_questions'] = questions
            current_app.logger.info('Generated %d new questions', len(questions))
            print(f'Generated {len(questions)} questions')
        except Exception:
            current_app.logger.exception('Failed to generate questions from skills')
            questions = []

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
        'isLastQuestion': question_number >= 4
    })


@interview_bp.route('/api/tts', methods=['POST'])
@login_required
def api_tts():
    data = request.json
    text = data.get('text', '')
    audio_url = tts_synthesize(text)
    return jsonify({'audio_url': audio_url})


@interview_bp.route('/api/stt', methods=['POST'])
@login_required
def api_stt():
    if 'audio' not in request.files:
        return jsonify({'error': 'no audio'}), 400
    audio = request.files['audio']
    transcript = stt_transcribe(audio)
    return jsonify({'transcript': transcript})


@interview_bp.route('/api/evaluate', methods=['POST'])
@login_required
def api_evaluate():
    data = request.json
    question = data.get('question', '')
    answer = data.get('answer', '')
    question_number = data.get('questionNumber', 0)

    # Get evaluation from Gemini
    result = evaluate_answer(question, answer)

    # Compute a simple overall score on a 1-10 scale based on Gemini scores
    def _compute_overall_score(result_dict, answer_text: str) -> float:
        try:
            c = float(result_dict.get('confidence', 0))
            t = float(result_dict.get('technical', 0))
            com = float(result_dict.get('communication', 0))
        except Exception:
            c, t, com = 0.0, 0.0, 0.0

        words = len((answer_text or "").split())

        if words == 0:
            return 1.0
        if words <= 2:
            return 2.0

        avg_pct = (c + t + com) / 3.0  # 0-100
        base_score = round(max(1.0, min(10.0, avg_pct / 10.0)), 1)

        if avg_pct >= 75:
            return max(base_score, 8.0)
        if 45 <= avg_pct < 75:
            return max(base_score, 5.0)
        return base_score

    overall_score_10 = _compute_overall_score(result, answer)
    result['overall_score'] = overall_score_10

    # Store in session to track progress
    session_results = session.get('interview_results', [])
    session_results.append({
        'question': question,
        'answer': answer,
        'transcript': answer,
        'result': result,
        'overall_score': overall_score_10,
        'questionNumber': question_number
    })
    session['interview_results'] = session_results

    # If this was the last question (5th), run batch evaluation and persist
    if question_number >= 4:
        try:
            all_skills    = session.get('skills', [])
            all_questions = session.get('interview_questions', [])
            all_answers   = [r.get('answer', '') for r in session_results]

            # Comprehensive post-interview evaluation
            full_evaluation = evaluate_full_interview(all_skills, all_questions, all_answers)

            run_doc = {
                'user_email':      current_user.email,
                'created_at':      datetime.datetime.utcnow(),
                'skills':          all_skills,
                'questions':       all_questions,
                'results':         session_results,
                'full_evaluation': full_evaluation,
                'summary': {
                    'total_questions': len(session_results),
                }
            }
            interview_runs.insert_one(run_doc)
            session.pop('interview_results', None)
            result['redirect'] = url_for('interview.results_page')
        except Exception:
            current_app.logger.exception('Failed to persist interview run')

    return jsonify({'result': result, 'questionNumber': question_number})


@interview_bp.route('/results')
@login_required
def results_page():
    latest_run = interview_runs.find_one({'user_email': current_user.email}, sort=[('created_at', -1)])
    if latest_run:
        results         = latest_run.get('results', [])
        full_evaluation = latest_run.get('full_evaluation', None)
    else:
        user_doc        = users.find_one({'email': current_user.email})
        results         = user_doc.get('results', []) if user_doc else []
        full_evaluation = None

    return render_template('result.html', results=results, full_evaluation=full_evaluation)
