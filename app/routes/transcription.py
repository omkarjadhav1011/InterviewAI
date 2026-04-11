from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.services import transcription_service

transcription_bp = Blueprint("transcription", __name__)


@transcription_bp.route("/start_transcription", methods=["POST"])
@login_required
def start_transcription():
    result = transcription_service.start_transcription()
    code = 500 if result.get("status") == "error" else 200
    return jsonify(result), code


@transcription_bp.route("/stop_transcription", methods=["POST"])
@login_required
def stop_transcription():
    result = transcription_service.stop_transcription()
    code = 500 if result.get("status") == "error" else 200
    return jsonify(result), code


@transcription_bp.route("/update_transcript", methods=["POST"])
@login_required
def update_transcript():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str):
        return jsonify({"status": "error", "error": "text must be a string"}), 400
    transcription_service.update_transcript(text)
    return jsonify({"status": "ok"})
