"""JSON results & interview-lifecycle endpoints (additive — no FE coupling).

These supplement the existing HTML `/results` page and the session-driven
flow inside /api/evaluate. They do not replace any current behavior.
"""
from flask import Blueprint, jsonify, current_app, session
from flask_login import login_required, current_user

from ..extensions import get_db

results_api_bp = Blueprint('results_api', __name__)


def _err(message: str, code: int = 400):
    return jsonify({'status': 'error', 'error': message}), code


def _ok(**payload):
    return jsonify({'status': 'ok', **payload})


def _shape_results(run_doc: dict) -> dict:
    """Map an interview_runs document to the flat /api/results response shape.

    Reads `final_scores` when present (new docs) and reconstructs from
    `full_evaluation`/`results[]` for older documents that predate this change.
    """
    final = run_doc.get('final_scores') or {}
    full_eval = run_doc.get('full_evaluation') or {}
    overall_eval = full_eval.get('overall_evaluation') or {}

    if final:
        overall_score = final.get('overall_score')
        confidence = final.get('confidence_avg')
        technical = final.get('technical_avg')
        communication = final.get('communication_avg')
        recommendation = final.get('hire_recommendation')
        feedback = final.get('overall_feedback', '')
        strengths = final.get('strengths', [])
        improvements = final.get('areas_for_improvement', [])
    else:
        # Reconstruct from per-question results for older docs
        results = run_doc.get('results') or []
        confs, techs, comms, overalls = [], [], [], []
        for r in results:
            res = (r or {}).get('result') or {}
            try:
                confs.append(float(res.get('confidence', 0)))
                techs.append(float(res.get('technical', 0)))
                comms.append(float(res.get('communication', 0)))
            except (TypeError, ValueError):
                pass
            try:
                overalls.append(float(r.get('overall_score', 0)))
            except (TypeError, ValueError):
                pass
        n = max(len(results), 1)
        confidence = round(sum(confs) / n, 1) if confs else 0
        technical = round(sum(techs) / n, 1) if techs else 0
        communication = round(sum(comms) / n, 1) if comms else 0
        overall_score = round(sum(overalls) / n, 1) if overalls else 0
        verdict = (overall_eval.get('verdict') or '').lower().replace(' ', '_')
        recommendation = {
            'strong_hire': 'strong_yes',
            'hire': 'yes',
            'weak_hire': 'maybe',
            'reject': 'no',
        }.get(verdict, 'maybe')
        feedback = overall_eval.get('summary', '')
        strengths = []
        improvements = []

    per_question = []
    for r in (run_doc.get('results') or []):
        res = (r or {}).get('result') or {}
        per_question.append({
            'question_id': r.get('questionNumber', 0),
            'question_text': r.get('question', ''),
            'combined_answer': r.get('answer', ''),
            'scores': {
                'confidence': res.get('confidence'),
                'technical': res.get('technical'),
                'communication': res.get('communication'),
                'overall': r.get('overall_score'),
            },
            'feedback': res.get('feedback', ''),
            'key_strength': res.get('key_strength', ''),
            'key_gap': res.get('key_gap', ''),
        })

    created_at = run_doc.get('created_at')
    if hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()

    return {
        'overall_score': overall_score,
        'confidence': confidence,
        'technical': technical,
        'communication': communication,
        'hire_recommendation': recommendation,
        'overall_feedback': feedback,
        'strengths': strengths,
        'areas_for_improvement': improvements,
        'per_question': per_question,
        'skills': run_doc.get('skills', []),
        'created_at': created_at,
    }


@results_api_bp.route('/api/results', methods=['GET'])
@login_required
def get_results():
    db = get_db()
    run = db.interview_runs.find_one(
        {'user_email': current_user.email},
        sort=[('created_at', -1)],
    )
    if not run:
        return _err('No interview results found', 404)
    try:
        return _ok(**_shape_results(run))
    except Exception:
        current_app.logger.exception('Error shaping /api/results response')
        return _err('Internal server error', 500)


@results_api_bp.route('/api/interview/start', methods=['POST'])
@login_required
def interview_start():
    """Return the questions stored in the current session.

    No state mutation — the upload handler already populated session keys.
    """
    questions = session.get('interview_questions', []) or []
    return _ok(questions=questions, session_id=session.get('_id') or '')


@results_api_bp.route('/api/interview/complete', methods=['POST'])
@login_required
def interview_complete():
    """Idempotent confirmation that the most recent run was persisted.

    The actual write happens inside /api/evaluate on the last question
    (session-first design). This endpoint exists so a client can confirm
    the run_id without inspecting the session.
    """
    db = get_db()
    run = db.interview_runs.find_one(
        {'user_email': current_user.email, 'completed': True},
        sort=[('created_at', -1)],
        projection={'_id': 1, 'created_at': 1},
    )
    if not run:
        return _err('Interview not yet completed', 409)
    return _ok(run_id=str(run['_id']))
