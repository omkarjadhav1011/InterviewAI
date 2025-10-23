import requests
import os

VAPI_API_KEY = os.getenv("VAPI_API_KEY")

def stt_transcribe(audio_file):
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
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"STT failed: {e}"
def tts_synthesize(text):
    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "text": text,
            "voice": "default",  # Or your custom voice ID
            "language": "en"
        }

        response = requests.post(
            "https://api.vapi.ai/text-to-speech",
            headers=headers,
            json=data,
        )

        if response.ok:
            return response.json().get("audio_url", None)
        else:
            return None
    except Exception as e:
        return None
