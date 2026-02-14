from flask import Blueprint, jsonify, request
from app.services import transcription_service

transcription_bp = Blueprint("transcription", __name__)

@transcription_bp.route("/start_transcription", methods=["POST"])
def start_transcription():
    result = transcription_service.start_transcription()
    return jsonify(result)

@transcription_bp.route("/stop_transcription", methods=["POST"])
def stop_transcription():
    result = transcription_service.stop_transcription()
    return jsonify(result)

@transcription_bp.route("/update_transcript", methods=["POST"])
def update_transcript():
    data = request.json or {}
    text = data.get("text", "")
    transcription_service.update_transcript(text)
    return jsonify({"status": "ok"})
