from flask import Blueprint, jsonify
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
