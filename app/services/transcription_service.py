import requests
import logging

# ─── Configuration ───────────────────────────────────────────────
API_KEY = "2b02b14d7451446a8d217f2bb8fa9054"
SAMPLE_RATE = 16000

# ─── Logging Setup ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ─── Global Variables ────────────────────────────────────────────
final_transcript = ""


def start_transcription():
    """
    Request a temporary authentication token from AssemblyAI and return
    a v3 Universal-Streaming WebSocket URL for the browser to connect to.
    """
    global final_transcript
    final_transcript = ""

    try:
        # Create a temporary token for browser-side auth
        response = requests.post(
            "https://api.assemblyai.com/v2/realtime/token",
            json={"expires_in": 3600},
            headers={
                "authorization": API_KEY,
                "content-type": "application/json"
            }
        )

        if response.ok:
            token = response.json().get("token")
            # Use the v3 Universal-Streaming endpoint
            ws_url = (
                f"wss://streaming.assemblyai.com/v3/ws"
                f"?sample_rate={SAMPLE_RATE}"
                f"&token={token}"
                f"&encoding=pcm_s16le"
                f"&language=en"
            )
            logging.info("Created real-time transcription token (v3)")
            return {"status": "started", "ws_url": ws_url}
        else:
            logging.error(f"Failed to get token: {response.status_code} {response.text}")
            # Fallback: let the browser connect directly with the API key
            ws_url = (
                f"wss://streaming.assemblyai.com/v3/ws"
                f"?sample_rate={SAMPLE_RATE}"
                f"&token={API_KEY}"
                f"&encoding=pcm_s16le"
                f"&language=en"
            )
            logging.info("Using API key directly for WebSocket auth")
            return {"status": "started", "ws_url": ws_url}

    except Exception as e:
        logging.error(f"Failed to start transcription: {e}")
        return {"status": "error", "error": str(e)}


def stop_transcription():
    """
    Stop transcription. The WebSocket is managed client-side,
    so this returns the accumulated transcript.
    """
    global final_transcript
    logging.info("Transcription stop requested")
    return {"status": "stopped", "transcript": final_transcript.strip()}


def update_transcript(text):
    """Accumulate transcript text sent from the client."""
    global final_transcript
    if text:
        final_transcript += text + " "
