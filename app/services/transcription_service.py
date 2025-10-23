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

logging.basicConfig(level=logging.INFO)

api_key = "2b02b14d7451446a8d217f2bb8fa9054"
transcript_text = ""
client = None
stream_thread = None
is_streaming = False


def on_begin(self, event: BeginEvent):
    print(f"Session started: {event.id}")


def on_turn(self, event: TurnEvent):
    global transcript_text
    if event.transcript:
        transcript_text += event.transcript + " "
        print(event.transcript)


def on_terminated(self, event: TerminationEvent):
    print(f"Session terminated after {event.audio_duration_seconds}s")


def on_error(self, error: StreamingError):
    print(f"Error: {error}")


def _stream_audio():
    global client, is_streaming
    client = StreamingClient(
        StreamingClientOptions(api_key=api_key, api_host="streaming.assemblyai.com")
    )

    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    client.connect(StreamingParameters(sample_rate=16000, format_turns=True))
    print("🎙️ Streaming started...")

    try:
        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))
    except Exception as e:
        print("Streaming stopped:", e)
    finally:
        client.disconnect(terminate=True)
        is_streaming = False
        print("✅ Streaming session closed.")


def start_transcription():
    global is_streaming, stream_thread, transcript_text
    if not is_streaming:
        transcript_text = ""
        is_streaming = True
        stream_thread = threading.Thread(target=_stream_audio)
        stream_thread.start()
        return {"status": "started"}
    return {"status": "already running"}


def stop_transcription():
    global client, is_streaming
    if client:
        client.disconnect(terminate=True)
        is_streaming = False
    return {"status": "stopped", "transcript": transcript_text}
