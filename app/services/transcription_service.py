import os
import requests
import logging

# ─── Configuration ───────────────────────────────────────────────
API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
SAMPLE_RATE = 16000

# ─── Logging Setup ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_ws_url() -> dict:
    """
    Request a temporary auth token from AssemblyAI and return the v3
    Universal-Streaming WebSocket URL.  Stateless — caller manages transcript.
    """
    if not API_KEY:
        return {"status": "error", "error": "ASSEMBLYAI_API_KEY not configured"}

    try:
        response = requests.post(
            "https://api.assemblyai.com/v2/realtime/token",
            json={"expires_in": 3600},
            headers={
                "authorization": API_KEY,
                "content-type": "application/json"
            },
            timeout=10,
        )

        if response.ok:
            token = response.json().get("token")
            logging.info("Created real-time transcription token (v3)")
        else:
            logging.error("Failed to get token: %s %s", response.status_code, response.text)
            return {"status": "error", "error": "Could not obtain transcription token"}

        ws_url = (
            f"wss://streaming.assemblyai.com/v3/ws"
            f"?sample_rate={SAMPLE_RATE}"
            f"&token={token}"
            f"&encoding=pcm_s16le"
            f"&language=en"
        )
        return {"status": "started", "ws_url": ws_url}

    except Exception as e:
        logging.error("Failed to start transcription: %s", e)
        return {"status": "error", "error": str(e)}
