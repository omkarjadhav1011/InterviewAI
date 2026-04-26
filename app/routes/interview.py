from flask import Blueprint, render_template, request, jsonify, current_app, session, url_for
from flask_login import login_required, current_user
from ..services.gemini_service import (
    generate_questions, evaluate_answer, evaluate_full_interview, compute_final_scores,
    regenerate_next_question,
)
from ..services.vapi_service import tts_synthesize, stt_transcribe
from ..extensions import get_db
import datetime

interview_bp = Blueprint('interview', __name__)


def combine_answers(voice_transcript: str, typed_answer: str) -> str:
    """Merge voice transcript and typed input into one answer string for evaluation.

    Cases:
      1. voice-only: return the voice transcript
      2. typed-only: return the typed answer
      3. one is a substring of the other: return the longer one (deduplicate)
      4. high word overlap (>60%): return the longer one
      5. distinct contributions: return "<typed> <voice>" (typed first - usually more deliberate)
      6. both empty: return ""
    """
    voice = (voice_transcript or "").strip()
    typed = (typed_answer or "").strip()

    if not voice and not typed:
        return ""
    if not typed:
        return voice
    if not voice:
        return typed

    if voice.lower() in typed.lower():
        return typed
    if typed.lower() in voice.lower():
        return voice

    voice_words = set(voice.lower().split())
    typed_words = set(typed.lower().split())
    if not voice_words or not typed_words:
        return typed if typed else voice

    overlap = len(voice_words & typed_words) / min(len(voice_words), len(typed_words))
    if overlap > 0.6:
        return typed if len(typed) >= len(voice) else voice

    return f"{typed} {voice}"


@interview_bp.route('/interview')
@login_required
def interview_page():
    users = get_db().users
    user_doc = users.find_one({'email': current_user.email})
    return render_template('interview.html', user=user_doc)


def _get_candidate_profile():
    """Pull the structured profile from session, falling back to DB lookup."""
    profile = session.get('candidate_profile')
    if profile:
        return profile
    db = get_db()
    resume_doc = db.resumes.find_one({'user_email': current_user.email}) or {}
    user_doc = db.users.find_one({'email': current_user.email}) or {}
    skills = resume_doc.get('skills') or user_doc.get('skills') or []
    return {
        'skills': skills,
        'name': resume_doc.get('name'),
        'summary': resume_doc.get('summary', ''),
        'experience_years': resume_doc.get('experience_years'),
        'job_titles': resume_doc.get('job_titles', []),
        'education': resume_doc.get('education', []),
    }


@interview_bp.route('/api/get_question')
@login_required
def api_get_question():
    try:
        profile = _get_candidate_profile()
        skills = profile.get('skills', []) or []
        seed = session.get('interview_seed')
        q = generate_questions(skills, count=7, profile=profile, session_seed=seed)
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
            profile = _get_candidate_profile()
            seed = session.get('interview_seed')
            questions = generate_questions(
                skills, count=5, profile=profile, session_seed=seed,
            )
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
    # When VAPI is unavailable, return audio_url=null so the frontend uses
    # its built-in SpeechSynthesisUtterance fallback without surfacing a 503.
    return jsonify({'status': 'ok', 'audio_url': audio_url, 'fallback': audio_url is None})


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
    skills_for_eval = session.get('skills') or []
    try:
        result = evaluate_answer(question, combined_answer, skills=skills_for_eval)
    except TypeError:
        # Backward-compat shim if a third-party fork passes only 2 args
        result = evaluate_answer(question, combined_answer)
    except TimeoutError:
        current_app.logger.warning('Gemini evaluation timed out')
        return jsonify({'status': 'error', 'error': 'AI service timed out, please try again'}), 503

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
    interview_questions = session.get('interview_questions', [])
    total_questions = len(interview_questions)
    is_last = question_number >= (total_questions - 1) if total_questions > 0 else question_number >= 4

    # Adaptive regeneration: rewrite the NEXT question based on the conversation
    # so far so it builds on what the candidate just said. Skip on the last
    # question; skip silently on any failure (the pre-generated question stands).
    if not is_last and total_questions > 0:
        try:
            next_index = question_number + 1
            if next_index < total_questions:
                history = []
                for r in session_results:
                    history.append({
                        'question': r.get('question', ''),
                        'answer': r.get('answer', ''),
                    })
                profile = _get_candidate_profile()
                fallback = interview_questions[next_index]
                new_q = regenerate_next_question(
                    profile=profile,
                    skills=profile.get('skills', []) or [],
                    previous_qa=history,
                    next_index=next_index,
                    total_questions=total_questions,
                    fallback_question=fallback,
                )
                if new_q and new_q != fallback:
                    interview_questions[next_index] = new_q
                    session['interview_questions'] = interview_questions
                    current_app.logger.info(
                        'Regenerated adaptive Q%d based on prior answers', next_index + 1,
                    )
        except Exception:
            current_app.logger.exception('Adaptive next-question regen failed (non-fatal)')

    response_payload = {
        'status': 'ok',
        'result': result,
        'questionNumber': question_number,
        'is_last_question': bool(is_last),
        'combined_answer': combined_answer,
    }

    if is_last:
        try:
            db = get_db()
            all_skills    = session.get('skills', [])
            all_questions = session.get('interview_questions', [])
            answer_map    = {r.get('questionNumber', i): r.get('answer', '') for i, r in enumerate(session_results)}
            all_answers   = [answer_map.get(i, '') for i in range(len(all_questions))]

            full_evaluation = evaluate_full_interview(all_skills, all_questions, all_answers)
            final_scores = compute_final_scores(session_results, full_evaluation)

            run_doc = {
                'user_email':      current_user.email,
                'created_at':      datetime.datetime.utcnow(),
                'skills':          all_skills,
                'questions':       all_questions,
                'results':         session_results,
                'full_evaluation': full_evaluation,
                'final_scores':    final_scores,
                'completed':       True,
                'summary': {
                    'total_questions': len(session_results),
                }
            }
            duration = session.get('interview_duration_seconds')
            if duration is not None:
                run_doc['duration_seconds'] = duration
            db.interview_runs.insert_one(run_doc)
            session.pop('interview_results', None)
        except Exception:
            current_app.logger.exception('Failed to persist interview run')

        result['redirect'] = url_for('interview.results_page')
        response_payload['redirect'] = result['redirect']

    return jsonify(response_payload)


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
