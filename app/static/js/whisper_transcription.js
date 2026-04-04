// ======================================================
// whisper_transcription.js
// Offline STT via Xenova/whisper-base (Transformers.js CDN)
// Exposes: window.WhisperSTT = { initWhisper, startRecording, stopRecording }
// ======================================================

let transcriber = null;
let mediaRecorder = null;
let recordingMimeType = "";
let audioChunks = [];
let isRecording = false;
let statusCallback = null;

// Web Speech API fallback state
let usingSpeechFallback = false;
let recognition = null;
let recognitionTranscript = "";

function setStatus(state, detail) {
  if (statusCallback) statusCallback(state, detail);
}

// -------------------------------------------------------
// initWhisper(onStatus) → Promise<boolean>
// Loads Transformers.js + whisper-base model.
// Falls back to Web Speech API if CDN import fails.
// -------------------------------------------------------
async function initWhisper(onStatus) {
  statusCallback = onStatus || null;
  setStatus("loading");

  try {
    const { pipeline, env } = await import(
      "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.1"
    );

    env.allowLocalModels = false;

    transcriber = await pipeline(
      "automatic-speech-recognition",
      "Xenova/whisper-base",
      {
        progress_callback: (progress) => {
          if (progress.status === "downloading") {
            setStatus("downloading", progress);
          }
        },
      }
    );

    setStatus("ready");
    return true;
  } catch (err) {
    console.warn("Whisper (Transformers.js) failed to load:", err);
    return _initSpeechFallback();
  }
}

// -------------------------------------------------------
// Web Speech API fallback
// -------------------------------------------------------
function _initSpeechFallback() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    setStatus("error");
    return false;
  }

  usingSpeechFallback = true;
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = "en-US";

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        recognitionTranscript += event.results[i][0].transcript + " ";
      }
    }
  };

  recognition.onerror = (event) => {
    console.warn("Web Speech API error:", event.error);
  };

  setStatus("ready-fallback");
  return true;
}

// -------------------------------------------------------
// startRecording(stream) — begin capturing audio
// -------------------------------------------------------
async function startRecording(stream) {
  if (isRecording) return;
  isRecording = true;

  if (usingSpeechFallback) {
    recognitionTranscript = "";
    try {
      recognition.start();
    } catch (e) {
      // already started — ignore
    }
    return;
  }

  audioChunks = [];
  recordingMimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm"
    : MediaRecorder.isTypeSupported("audio/ogg;codecs=opus") ? "audio/ogg;codecs=opus"
    : "";

  try {
    mediaRecorder = recordingMimeType
      ? new MediaRecorder(stream, { mimeType: recordingMimeType })
      : new MediaRecorder(stream);
  } catch (e) {
    mediaRecorder = new MediaRecorder(stream);
    recordingMimeType = "";
  }

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) audioChunks.push(e.data);
  };

  mediaRecorder.start(500);
}

// -------------------------------------------------------
// stopRecording() → Promise<string>  (the transcribed text)
// -------------------------------------------------------
async function stopRecording() {
  if (!isRecording) return "";
  isRecording = false;

  if (usingSpeechFallback) {
    await new Promise((resolve) => {
      recognition.onend = resolve;
      try { recognition.stop(); } catch (e) { resolve(); }
    });
    return recognitionTranscript.trim();
  }

  // Whisper path: stop recorder, decode, transcribe
  return new Promise((resolve) => {
    if (!mediaRecorder) {
      resolve("");
      return;
    }

    mediaRecorder.onstop = async () => {
      try {
        const blob = new Blob(audioChunks, { type: recordingMimeType || "audio/webm" });

        if (blob.size === 0) {
          resolve("");
          return;
        }

        const arrayBuffer = await blob.arrayBuffer();

        const audioCtx = new AudioContext({ sampleRate: 16000 });
        let audioBuffer;
        try {
          audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        } catch (decodeErr) {
          console.warn("Audio decode failed:", decodeErr);
          audioCtx.close();
          resolve("");
          return;
        }
        const float32 = audioBuffer.getChannelData(0);
        audioCtx.close();

        setStatus("transcribing");
        const result = await transcriber(float32, { sampling_rate: 16000 });
        setStatus("ready");
        resolve((result && result.text) ? result.text.trim() : "");
      } catch (err) {
        console.error("Whisper transcription error:", err);
        setStatus("ready");
        resolve("");
      }
    };

    mediaRecorder.stop();
  });
}

// -------------------------------------------------------
// Expose globally so classic (non-module) scripts can use it
// -------------------------------------------------------
window.WhisperSTT = { initWhisper, startRecording, stopRecording };
