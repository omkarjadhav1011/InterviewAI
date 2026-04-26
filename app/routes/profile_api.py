"""Read-only JSON endpoints for the candidate profile and interview history.

Additive — current frontend does not call these. Useful for future surfaces
(e.g. a candidate dashboard, a CLI inspector, or a 3rd-party integration).
"""
from flask import Blueprint, jsonify, session, current_app
from flask_login import login_required, current_user

from ..extensions import get_db

profile_api_bp = Blueprint('profile_api', __name__)


def _err(message: str, code: int = 400):
    return jsonify({'status': 'error', 'error': message}), code


def _ok(**payload):
    return jsonify({'status': 'ok', **payload})


@profile_api_bp.route('/api/resume/profile', methods=['GET'])
@login_required
def resume_profile():
    db = get_db()
    doc = db.resumes.find_one({'user_email': current_user.email})
    if not doc:
        return _err('No resume on file for this user', 404)
    parsed_at = doc.get('parsed_at')
    if hasattr(parsed_at, 'isoformat'):
        parsed_at = parsed_at.isoformat()
    return _ok(
        skills=doc.get('skills', []),
        name=doc.get('name'),
        summary=doc.get('summary', ''),
        experience_years=doc.get('experience_years'),
        job_titles=doc.get('job_titles', []),
        education=doc.get('education', []),
        filename=doc.get('filename', ''),
        parsed_at=parsed_at,
    )


@profile_api_bp.route('/api/interview/history', methods=['GET'])
@login_required
def interview_history():
    db = get_db()
    cursor = db.interview_runs.find(
        {'user_email': current_user.email},
        projection={
            '_id': 1,
            'created_at': 1,
            'skills': 1,
            'final_scores.overall_score': 1,
            'final_scores.hire_recommendation': 1,
            'full_evaluation.overall_evaluation.final_score': 1,
            'full_evaluation.overall_evaluation.verdict': 1,
        },
        sort=[('created_at', -1)],
        limit=5,
    )
    runs = []
    for doc in cursor:
        final_scores = doc.get('final_scores') or {}
        full_eval = (doc.get('full_evaluation') or {}).get('overall_evaluation') or {}
        overall_score = final_scores.get('overall_score')
        if overall_score is None:
            # Older docs only have full_evaluation.overall_evaluation.final_score (0-100)
            try:
                overall_score = round(float(full_eval.get('final_score', 0)) / 10.0, 1)
            except (TypeError, ValueError):
                overall_score = None
        recommendation = final_scores.get('hire_recommendation') or {
            'strong hire': 'strong_yes',
            'hire': 'yes',
            'weak hire': 'maybe',
            'reject': 'no',
        }.get((full_eval.get('verdict') or '').lower(), None)

        created_at = doc.get('created_at')
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        runs.append({
            'run_id': str(doc.get('_id')),
            'created_at': created_at,
            'overall_score': overall_score,
            'skills': doc.get('skills', []),
            'hire_recommendation': recommendation,
        })
    return _ok(history=runs)


@profile_api_bp.route('/api/resume/questions/status', methods=['GET'])
@login_required
def resume_questions_status():
    """Synchronous-by-design status endpoint.

    /upload generates questions in-request and stashes them in the session, so
    this endpoint always reports "ready" once the user has uploaded a resume.
    Spec-compliant stub for any future frontend that polls.
    """
    questions = session.get('interview_questions') or []
    status = 'ready' if questions else 'not_started'
    return _ok(status=status, questions=questions)
