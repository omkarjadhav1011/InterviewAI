import requests
import os
import logging

logger = logging.getLogger(__name__)

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
VAPI_VOICE_ID = os.getenv("VAPI_VOICE_ID", "")
VAPI_VOICE_PROVIDER = os.getenv("VAPI_VOICE_PROVIDER", "11labs")

VAPI_STT_URL = "https://api.vapi.ai/speech-to-text"
VAPI_TTS_URL = "https://api.vapi.ai/speech/generate"


def stt_transcribe(audio_file):
    """Transcribe audio via VAPI. Returns transcript string on success, None on failure."""
    if not VAPI_API_KEY:
        return None
    try:
        audio_bytes = audio_file.read()
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "audio/wav",
        }
        response = requests.post(
            VAPI_STT_URL,
            headers=headers,
            data=audio_bytes,
            timeout=15,
        )
        if response.ok:
            return response.json().get("transcript", "")
        logger.warning("STT request failed: %s %s", response.status_code, response.text[:200])
        return None
    except Exception:
        logger.exception("STT transcription error")
        return None


def tts_synthesize(text):
    """
    Synthesize text to audio via VAPI. Returns an audio URL string on success,
    or None on failure (caller should fall back to browser TTS).

    VAPI does not currently expose a stable public REST endpoint for one-shot
    TTS that returns an audio URL. If VAPI_VOICE_ID is not configured, we skip
    the call entirely so the frontend falls back to its built-in browser TTS
    without log spam.
    """
    if not VAPI_API_KEY or not VAPI_VOICE_ID:
        logger.debug("VAPI TTS skipped (missing VAPI_API_KEY or VAPI_VOICE_ID); using browser fallback")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": text,
            "voice": {
                "provider": VAPI_VOICE_PROVIDER,
                "voiceId": VAPI_VOICE_ID,
            },
        }
        response = requests.post(
            VAPI_TTS_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        if response.ok:
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return body.get("audio_url") or body.get("url")
        logger.warning("TTS request failed: %s %s", response.status_code, response.text[:200])
        return None
    except Exception:
        logger.exception("TTS synthesis error")
        return None
