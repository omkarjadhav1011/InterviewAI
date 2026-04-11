from flask import Blueprint, render_template, request, jsonify, current_app, session, url_for
from flask_login import login_required, current_user
from ..services.gemini_service import generate_questions, evaluate_answer, evaluate_full_interview
from ..services.vapi_service import tts_synthesize, stt_transcribe
from ..extensions import get_db
import datetime

interview_bp = Blueprint('interview', __name__)


def combine_answers(transcript: str, typed: str) -> str:
    """Merge voice transcript and typed input into one answer string."""
    t = (transcript or "").strip()
    d = (typed or "").strip()
    if not t and not d:
        return ""
    if not t:
        return d
    if not d:
        return t
    if d.lower() in t.lower() or t.lower() in d.lower():
        return t if len(t) >= len(d) else d
    return f"{t}\n\n[Typed supplement]: {d}"


@interview_bp.route('/interview')
@login_required
def interview_page():
    users = get_db().users
    user_doc = users.find_one({'email': current_user.email})
    return render_template('interview.html', user=user_doc)


@interview_bp.route('/api/get_question')
@login_required
def api_get_question():
    try:
        users = get_db().users
        user_doc = users.find_one({'email': current_user.email})
        skills = user_doc.get('skills', []) if user_doc else []
        q = generate_questions(skills, count=7)
        return jsonify({'status': 'ok', 'questions': q})
    except Exception:
        current_app.logger.exception('Failed to generate questions')
        return jsonify({'status': 'error', 'error': 'failed to generate questions'}), 500


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
        users = get_db().users
        user_doc = users.find_one({'email': current_user.email})
        if user_doc:
            skills = user_doc.get('skills', [])
    current_app.logger.debug('Available skills: %s', len(skills) if skills else 0)

    if skills and not questions:
        try:
            questions = generate_questions(skills, count=5)
            session['interview_questions'] = questions
            current_app.logger.info('Generated %d new questions', len(questions))
        except Exception:
            current_app.logger.exception('Failed to generate questions from skills')
            questions = []

    total = len(questions) if questions else 0
    current_question = questions[question_number] if questions and question_number < total else None
    is_last = question_number >= (total - 1) if total > 0 else False

    return jsonify({
        'status': 'ok',
        'currentQuestion': current_question,
        'questionNumber': question_number,
        'totalQuestions': total,
        'progress': {
            'current': question_number + 1,
            'total': total,
            'completed': (question_number / total * 100) if total > 0 else 0
        },
        'skills': skills,
        'isLastQuestion': is_last
    })


@interview_bp.route('/api/tts', methods=['POST'])
@login_required
def api_tts():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'error': 'missing JSON body'}), 400
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'status': 'error', 'error': 'text is required'}), 400
    audio_url = tts_synthesize(text)
    if audio_url is None:
        return jsonify({'status': 'error', 'error': 'TTS service unavailable'}), 503
    return jsonify({'status': 'ok', 'audio_url': audio_url})


@interview_bp.route('/api/stt', methods=['POST'])
@login_required
def api_stt():
    if 'audio' not in request.files:
        return jsonify({'status': 'error', 'error': 'no audio'}), 400
    audio = request.files['audio']
    transcript = stt_transcribe(audio)
    if transcript and (transcript.startswith('Error:') or transcript.startswith('STT failed:')):
        current_app.logger.warning('STT service error: %s', transcript)
        return jsonify({'status': 'error', 'error': 'transcription failed'}), 503
    return jsonify({'status': 'ok', 'transcript': transcript or ''})


@interview_bp.route('/api/evaluate', methods=['POST'])
@login_required
def api_evaluate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'error': 'missing JSON body'}), 400

    question = data.get('question', '')
    answer = data.get('answer', '')
    question_number = data.get('questionNumber', 0)
    typed_answer = data.get('typed_answer', '')

    if not question:
        return jsonify({'status': 'error', 'error': 'question is required'}), 400
    if not isinstance(question_number, int) or question_number < 0:
        return jsonify({'status': 'error', 'error': 'invalid questionNumber'}), 400

    # Combine voice transcript and typed input, then evaluate
    combined_answer = combine_answers(answer, typed_answer)
    result = evaluate_answer(question, combined_answer)

    def _compute_overall_score(result_dict, answer_text: str) -> float:
        try:
            c = float(result_dict.get('confidence', 0))
            t = float(result_dict.get('technical', 0))
            com = float(result_dict.get('communication', 0))
        except (ValueError, TypeError):
            c, t, com = 0.0, 0.0, 0.0

        words = len((answer_text or "").split())

        if words == 0:
            return 1.0
        if words <= 2:
            return 2.0

        avg_pct = (c + t + com) / 3.0
        base_score = round(max(1.0, min(10.0, avg_pct / 10.0)), 1)

        if avg_pct >= 75:
            return max(base_score, 8.0)
        if 45 <= avg_pct < 75:
            return max(base_score, 5.0)
        return base_score

    overall_score_10 = _compute_overall_score(result, combined_answer)
    result['overall_score'] = overall_score_10

    # Store in session to track progress (cap to avoid unbounded growth)
    session_results = session.get('interview_results', [])
    session_results.append({
        'question':       question,
        'answer':         combined_answer,
        'transcript':     answer,
        'typed':          typed_answer,
        'final':          combined_answer,
        'result':         result,
        'overall_score':  overall_score_10,
        'questionNumber': question_number
    })
    # Safety cap: keep only latest N results where N = total questions
    total_q = len(session.get('interview_questions', []))
    max_results = max(total_q, 10)
    session['interview_results'] = session_results[-max_results:]

    # Determine if this is the last question
    total_questions = len(session.get('interview_questions', []))
    is_last = question_number >= (total_questions - 1) if total_questions > 0 else question_number >= 4

    if is_last:
        try:
            db = get_db()
            all_skills    = session.get('skills', [])
            all_questions = session.get('interview_questions', [])
            answer_map    = {r.get('questionNumber', i): r.get('answer', '') for i, r in enumerate(session_results)}
            all_answers   = [answer_map.get(i, '') for i in range(len(all_questions))]

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
            db.interview_runs.insert_one(run_doc)
            session.pop('interview_results', None)
        except Exception:
            current_app.logger.exception('Failed to persist interview run')

        result['redirect'] = url_for('interview.results_page')

    return jsonify({'status': 'ok', 'result': result, 'questionNumber': question_number})


@interview_bp.route('/results')
@login_required
def results_page():
    db = get_db()
    latest_run = db.interview_runs.find_one({'user_email': current_user.email}, sort=[('created_at', -1)])
    if latest_run:
        results         = latest_run.get('results', [])
        full_evaluation = latest_run.get('full_evaluation', None)
    else:
        user_doc        = db.users.find_one({'email': current_user.email})
        results         = user_doc.get('results', []) if user_doc else []
        full_evaluation = None

    return render_template('result.html', results=results, full_evaluation=full_evaluation)
