import os


def tts_synthesize(text):
    # TODO: Replace with VAPI Text-to-Speech API call. Return audio URL or base64 audio data.
    # For demo, return None so the client falls back to browser TTS
    return None


def stt_transcribe(audio_file):
    # TODO: Send audio bytes to VAPI Speech-to-Text and return transcript
    # For demo purposes read bytes and return a dummy transcript
    try:
        data = audio_file.read()
        # In real implementation we would call VAPI and return their transcript result
        return 'transcribed text (demo)'
    except Exception:
        return ''
