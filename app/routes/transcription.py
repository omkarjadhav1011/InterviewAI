from urllib.parse import parse_qs, urlparse

from flask import Blueprint, current_app, jsonify, request, session
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
    code = 503 if result.get("status") == "error" else 200
    return jsonify(result), code


@transcription_bp.route("/api/transcription/token", methods=["GET"])
@login_required
def api_transcription_token():
    """Return a short-lived AssemblyAI realtime token (NOT the API key).

    The legacy POST /start_transcription returns the same ws_url with the
    token embedded. This endpoint exposes the token explicitly for clients
    that want to construct their own ws URL or reuse the token.
    """
    result = get_ws_url()
    if result.get("status") == "error":
        return jsonify({"status": "error",
                        "error": result.get("error", "transcription unavailable")}), 503
    ws_url = result.get("ws_url", "")
    token = ""
    try:
        qs = parse_qs(urlparse(ws_url).query)
        token = (qs.get("token") or [""])[0]
    except Exception:
        current_app.logger.exception("Failed to parse ws_url token")
    expires_in = current_app.config.get("ASSEMBLYAI_TOKEN_TTL", 55)
    return jsonify({
        "status": "ok",
        "token": token,
        "ws_url": ws_url,
        "expires_in": expires_in,
    })


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
