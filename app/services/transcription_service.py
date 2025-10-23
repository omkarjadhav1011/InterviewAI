import threading
import assemblyai as aai
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
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Variables ---
api_key = "2b02b14d7451446a8d217f2bb8fa9054"  # Replace with your key
transcript_text = ""  # Accumulate final turns
client = None
stream_thread = None
is_streaming = False

# --- Event Handlers ---
def on_begin(client, event: BeginEvent):
    logging.info(f"Session started: {event.id}")

def on_turn(client, event: TurnEvent):
    global transcript_text
    if event.transcript:
        transcript_text += event.transcript + " "

def on_terminated(client, event: TerminationEvent):
    logging.info(f"Session terminated after {event.audio_duration_seconds}s")

def on_error(client, error: StreamingError):
    logging.error(f"Streaming Error: {error}")

# --- Core Streaming Logic ---
def _stream_audio():
    global client, is_streaming
    try:
        client = StreamingClient(
            StreamingClientOptions(api_key=api_key, api_host="streaming.assemblyai.com")
        )

        # Attach event handlers
        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)

        # Connect and start streaming from microphone
        client.connect(StreamingParameters(sample_rate=16000, format_turns=True))
        logging.info("🎙 Streaming started... Speak into your microphone!")

        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))

    except Exception as e:
        logging.error(f"Streaming stopped unexpectedly: {e}")
    finally:
        if client:
            client.disconnect(terminate=True)
        is_streaming = False
        logging.info("✅ Streaming session closed.")

# --- Control Functions ---
def start_transcription():
    global is_streaming, stream_thread, transcript_text
    if not is_streaming:
        transcript_text = ""  # Clear previous transcript
        is_streaming = True
        stream_thread = threading.Thread(target=_stream_audio)
        stream_thread.start()
        logging.info("Transcription started in background.")
        return {"status": "started"}
    logging.warning("Transcription is already running.")
    return {"status": "already running"}

def stop_transcription():
    global client, is_streaming
    if client and is_streaming:
        logging.info("Stopping transcription...")
        client.disconnect(terminate=True)
        time.sleep(1)  # Give thread time to finish
        logging.info("Transcription stopped.")
        return {"status": "stopped", "transcript": transcript_text.strip()}
    logging.warning("Transcription was not running.")
    return {"status": "not running", "transcript": transcript_text.strip()}

# --- Example Usage ---
if __name__ == "__main__":
    print("--- AssemblyAI Real-time Transcription Demo ---")
    start_transcription()

    try:
        print("Streaming for 15 seconds. Press Ctrl+C to stop earlier.")
        time.sleep(15)
    except KeyboardInterrupt:
        print("\nUser interrupted transcription.")
    finally:
        final_result = stop_transcription()
        print("\n--- Final Full Transcript ---")
        print(final_result["transcript"])
        print("-----------------------------")

        # Ensure streaming thread finishes
        if stream_thread and stream_thread.is_alive():
            logging.info("Waiting for streaming thread to join...")
            stream_thread.join(timeout=5)
            if stream_thread.is_alive():
                logging.warning("Streaming thread did not terminate gracefully within timeout.")
