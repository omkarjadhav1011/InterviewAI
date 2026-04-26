import os
import requests
import logging

# ─── Configuration ───────────────────────────────────────────────
API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
SAMPLE_RATE = 16000
TOKEN_TTL_SECONDS = 600  # 10 minutes — within AssemblyAI's allowed range

# AssemblyAI v3 Universal-Streaming token endpoint
STREAMING_TOKEN_URL = "https://streaming.assemblyai.com/v3/token"
STREAMING_WS_HOST = "wss://streaming.assemblyai.com/v3/ws"

logger = logging.getLogger(__name__)


def get_ws_url() -> dict:
    """
    Request a temporary auth token from AssemblyAI's v3 Universal-Streaming
    API and return the WebSocket URL with the token embedded.
    """
    if not API_KEY:
        return {"status": "error", "error": "ASSEMBLYAI_API_KEY not configured"}

    try:
        response = requests.get(
            STREAMING_TOKEN_URL,
            params={"expires_in_seconds": TOKEN_TTL_SECONDS},
            headers={"authorization": API_KEY},
            timeout=10,
        )

        if not response.ok:
            logger.error(
                "Failed to get AssemblyAI streaming token: %s %s",
                response.status_code,
                response.text[:200],
            )
            return {"status": "error", "error": "Could not obtain transcription token"}

        token = response.json().get("token")
        if not token:
            logger.error("AssemblyAI token response missing 'token' field: %s", response.text[:200])
            return {"status": "error", "error": "Could not obtain transcription token"}

        ws_url = (
            f"{STREAMING_WS_HOST}"
            f"?sample_rate={SAMPLE_RATE}"
            f"&token={token}"
            f"&encoding=pcm_s16le"
            f"&format_turns=true"
        )
        logger.info("Created AssemblyAI v3 streaming token")
        return {"status": "started", "ws_url": ws_url}

    except requests.exceptions.Timeout:
        logger.error("AssemblyAI token request timed out")
        return {"status": "error", "error": "Transcription service timed out"}
    except Exception as e:
        logger.exception("Failed to start transcription")
        return {"status": "error", "error": str(e)}
