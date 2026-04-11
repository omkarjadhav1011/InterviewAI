from flask import Blueprint, jsonify, request, session
from flask_login import login_required
from app.services.transcription_service import get_ws_url

transcription_bp = Blueprint("transcription", __name__)

_SESSION_KEY = "live_transcript"


@transcription_bp.route("/start_transcription", methods=["POST"])
@login_required
def start_transcription():
    # Reset per-session transcript on each new recording
    session[_SESSION_KEY] = ""
    result = get_ws_url()
    code = 500 if result.get("status") == "error" else 200
    return jsonify(result), code


@transcription_bp.route("/stop_transcription", methods=["POST"])
@login_required
def stop_transcription():
    transcript = session.pop(_SESSION_KEY, "").strip()
    return jsonify({"status": "stopped", "transcript": transcript})


@transcription_bp.route("/update_transcript", methods=["POST"])
@login_required
def update_transcript():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str):
        return jsonify({"status": "error", "error": "text must be a string"}), 400
    if len(text) > 10_000:
        return jsonify({"status": "error", "error": "text too long"}), 400
    session[_SESSION_KEY] = session.get(_SESSION_KEY, "") + text + " "
    return jsonify({"status": "ok"})
