// ======================================================
// Combined interview.js with real-time transcription + AI logic
// ======================================================

// HTML elements
const cameraEl = document.getElementById('camera');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const nextBtn = document.getElementById('nextBtn');
const questionText = document.getElementById('question-text');
const transcriptDiv = document.getElementById('transcript');
const feedbackDiv = document.getElementById('feedback');
const qIndex = document.getElementById('qIndex');
const qTotal = document.getElementById('qTotal');

// Global state
let questions = [];
let current = 0;
let mediaStream = null;
let websocket = null;
let audioContext = null;
let processor = null;
let isRecording = false;

// ======================================================
// 🎥 CAMERA + AUDIO SETUP
// ======================================================
async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    cameraEl.srcObject = stream;
    mediaStream = stream;
  } catch (err) {
    console.error("Camera init failed:", err);
    alert("Camera or microphone access denied!");
  }
}

// ======================================================
// 🧠 LOAD INTERVIEW QUESTIONS
// ======================================================
async function loadQuestions() {
  try {
    const res = await fetch('/api/get_question');
    const data = await res.json();
    questions = data.questions || [];
    qTotal.innerText = questions.length;
    current = 0;
    showQuestion();
  } catch (err) {
    console.error("Error loading questions:", err);
  }
}


// New: Fetch questions from the session-backed endpoint `/get_questions` and
// render them into a simple <ul id="question-list"> if present on the page.
async function fetchAndRenderQuestions() {
  try {
    const res = await fetch('/get_questions');
    if (!res.ok) return;
    const data = await res.json();
    const serverQuestions = data.questions || [];

    // If an unordered list exists, render the questions there
    const list = document.getElementById('question-list');
    if (list && Array.isArray(serverQuestions)) {
      list.innerHTML = serverQuestions.map(q => `<li>${q}</li>`).join('');
    }

    // Also set the in-memory questions array used by the existing interview flow
    if (Array.isArray(serverQuestions) && serverQuestions.length) {
      questions = serverQuestions;
      if (qTotal) qTotal.innerText = questions.length;
      current = 0;
      showQuestion();
    }
  } catch (err) {
    console.error('Error fetching session questions:', err);
  }
}

// ======================================================
// 🗣 SHOW CURRENT QUESTION (with TTS playback)
// ======================================================
function showQuestion() {
  if (current >= questions.length) {
    window.location.href = '/results';
    return;
  }

  questionText.innerText = questions[current];
  qIndex.innerText = current + 1;

  // Play question via backend TTS or fallback
  fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: questions[current] })
  })
    .then(r => r.json())
    .then(d => {
      if (d.audio_url) {
        const audio = new Audio(d.audio_url);
        audio.play();
      } else {
        const utterance = new SpeechSynthesisUtterance(questions[current]);
        speechSynthesis.speak(utterance);
      }
    })
    .catch(err => console.error("TTS error:", err));
}

// ======================================================
// 🎧 START REAL-TIME TRANSCRIPTION
// ======================================================
async function startRecording() {
  if (isRecording) return;
  isRecording = true;

  transcriptDiv.textContent = "Listening...";
  feedbackDiv.textContent = "";
  startBtn.disabled = true;
  stopBtn.disabled = false;

  try {
    const response = await fetch('/start_transcription', { method: 'POST' });
    const { ws_url } = await response.json();

    websocket = new WebSocket(ws_url);

    websocket.onopen = () => {
      console.log("✅ Connected to WebSocket transcription session");
      streamAudioToWebSocket();
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.text) transcriptDiv.textContent = data.text;
    };

    websocket.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    websocket.onclose = () => {
      console.log("🛑 WebSocket closed");
    };
  } catch (err) {
    console.error("Error starting transcription:", err);
  }
}

// ======================================================
// 🎙 STREAM MICROPHONE AUDIO → WebSocket
// ======================================================
function streamAudioToWebSocket() {
  audioContext = new AudioContext({ sampleRate: 16000 });
  const source = audioContext.createMediaStreamSource(mediaStream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);

  source.connect(processor);
  processor.connect(audioContext.destination);

  processor.onaudioprocess = (e) => {
    if (!isRecording || !websocket || websocket.readyState !== WebSocket.OPEN) return;

    const inputData = e.inputBuffer.getChannelData(0);
    const buffer = new ArrayBuffer(inputData.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < inputData.length; i++) {
      const s = Math.max(-1, Math.min(1, inputData[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    websocket.send(buffer);
  };
}

// ======================================================
// ⏹ STOP TRANSCRIPTION + EVALUATE ANSWER
// ======================================================
async function stopRecording() {
  if (!isRecording) return;
  isRecording = false;

  startBtn.disabled = false;
  stopBtn.disabled = true;

  if (processor) processor.disconnect();
  if (audioContext) audioContext.close();
  if (websocket) websocket.close();

  try {
    await fetch('/stop_transcription', { method: 'POST' });
    console.log("✅ Streaming session closed");
  } catch (err) {
    console.error("Error stopping transcription:", err);
  }

  // Evaluate answer with Gemini
  const transcript = transcriptDiv.textContent;
  if (transcript && transcript.length > 0) {
    try {
      const evalRes = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: questions[current],
          answer: transcript
        })
      });
      const evalData = await evalRes.json();
      feedbackDiv.innerText = evalData.result || "Evaluation complete!";
    } catch (err) {
      feedbackDiv.innerText = "Error evaluating answer.";
      console.error("Evaluation error:", err);
    }
  }
}

// ======================================================
// ⏭ NEXT QUESTION
// ======================================================
nextBtn.addEventListener('click', () => {
  current++;
  showQuestion();
});

// ======================================================
// 🎬 EVENT LISTENERS
// ======================================================
startBtn.addEventListener('click', startRecording);
stopBtn.addEventListener('click', stopRecording);

// Initialize on page load
initCamera();
// Try to fetch questions from session/DB-backed endpoint first
fetchAndRenderQuestions();
