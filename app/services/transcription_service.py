import threading
import assemblyai as aai
import logging
import time
from assemblyai.streaming.v3 import (
    StreamingClient,
    StreamingClientOptions,
    StreamingParameters,
    StreamingEvents,
    BeginEvent,
    TurnEvent,
    TerminationEvent,
    StreamingError,
)

# ─── Configuration ───────────────────────────────────────────────
API_KEY = "2b02b14d7451446a8d217f2bb8fa9054"  # Replace securely with env variable
SAMPLE_RATE = 16000

# ─── Logging Setup ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ─── Global Variables ────────────────────────────────────────────
client = None
stream_thread = None
is_streaming = False
final_transcript = ""

# ─── Event Handlers ──────────────────────────────────────────────
def on_begin(client, event: BeginEvent):
    logging.info(f"Session started (ID: {event.id})")


def on_turn(client, event: TurnEvent):
    """
    Handle real-time Partial + Final (formatted) turn updates.
    Filters duplicates and prints final text only once (formatted).
    """
    global final_transcript

    if not event.transcript:
        return

    # Handle only formatted final turns — ignore partial + unformatted finals
    if event.turn_is_formatted and event.transcript.strip():
        final_text = event.transcript.strip()

        # Prevent repeated final text (API may resend same segment)
        if not final_transcript.endswith(final_text + " "):
            final_transcript += final_text + " "
            print(f"\n[FINAL] {final_text}\n")

    elif not event.turn_is_formatted and not event.end_of_turn:
        # Live partials: overwrite the same line
        print(f"\r[Partial] {event.transcript}", end="", flush=True)


def on_terminated(client, event: TerminationEvent):
    logging.info(f"Session terminated after {event.audio_duration_seconds:.2f} seconds")


def on_error(client, error: StreamingError):
    logging.error(f"Streaming Error: {error}")


# ─── Streaming Thread ────────────────────────────────────────────
def _stream_audio():
    global client, is_streaming
    try:
        client = StreamingClient(
            StreamingClientOptions(api_key=API_KEY, api_host="streaming.assemblyai.com")
        )

        # Bind event handlers
        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)

        # Connect with text formatting enabled
        client.connect(StreamingParameters(sample_rate=SAMPLE_RATE, format_turns=True))
        logging.info("🎙 Streaming started — speak into your microphone...")

        # Stream audio from microphone continuously
        client.stream(aai.extras.MicrophoneStream(sample_rate=SAMPLE_RATE))

    except Exception as e:
        logging.error(f"Streaming stopped unexpectedly: {e}")
    finally:
        if client:
            client.disconnect(terminate=True)
        is_streaming = False
        logging.info("✅ Streaming session closed.")


# ─── Control Functions ───────────────────────────────────────────
def start_transcription():
    global is_streaming, stream_thread, final_transcript
    if not is_streaming:
        final_transcript = ""
        is_streaming = True
        stream_thread = threading.Thread(target=_stream_audio, daemon=True)
        stream_thread.start()
        logging.info("Transcription thread started.")
        return {"status": "started"}
    else:
        logging.warning("Transcription already running.")
        return {"status": "already running"}


def stop_transcription():
    global client, is_streaming, final_transcript
    if client and is_streaming:
        logging.info("Stopping transcription...")
        client.disconnect(terminate=True)
        time.sleep(1)
        is_streaming = False
        logging.info("Transcription stopped.")
        return {"status": "stopped", "transcript": final_transcript.strip()}
    else:
        logging.warning("Transcription not running.")
        return {"status": "not running", "transcript": final_transcript.strip()}


# ─── Example Usage ───────────────────────────────────────────────
if __name__ == "__main__":
    print("--- AssemblyAI Real‑Time Transcription (Duplicate‑Fix Version) ---")
    start_transcription()

    try:
        print("Speak for 15 seconds... Press Ctrl+C to stop early.")
        time.sleep(15)
    except KeyboardInterrupt:
        print("\nUser manually interrupted transcription.")
    finally:
        result = stop_transcription()
        print("\n--- Final Transcript ---")
        print(result["transcript"])
        print("------------------------")

        if stream_thread and stream_thread.is_alive():
            stream_thread.join(timeout=3)
