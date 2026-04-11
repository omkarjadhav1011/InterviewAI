import requests
import os
import logging

logger = logging.getLogger(__name__)

VAPI_API_KEY = os.getenv("VAPI_API_KEY")


def stt_transcribe(audio_file):
    """Transcribe audio via VAPI. Returns transcript string on success, None on failure."""
    try:
        audio_bytes = audio_file.read()
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "audio/wav",
        }
        response = requests.post(
            "https://api.vapi.ai/speech-to-text",
            headers=headers,
            data=audio_bytes,
        )
        if response.ok:
            return response.json().get("transcript", "")
        logger.warning("STT request failed: %s %s", response.status_code, response.text)
        return None
    except Exception:
        logger.exception("STT transcription error")
        return None


def tts_synthesize(text):
    """Synthesize text to audio via VAPI. Returns audio_url string on success, None on failure."""
    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "text": text,
            "voice": "default",
            "language": "en"
        }
        response = requests.post(
            "https://api.vapi.ai/text-to-speech",
            headers=headers,
            json=data,
        )
        if response.ok:
            return response.json().get("audio_url", None)
        logger.warning("TTS request failed: %s %s", response.status_code, response.text)
        return None
    except Exception:
        logger.exception("TTS synthesis error")
        return None
