// ======================================================
// Combined interview.js with real-time transcription + AI logic
// ======================================================

// HTML elements - moved to DOMContentLoaded for reliability
let cameraEl;
let startBtn;
let stopBtn;
let nextBtn;
let questionText;
let transcriptDiv;
let feedbackDiv;
let qIndex;
let transcriptText;
let qTotal;

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
    // First try to get questions from /get_questions (session-backed)
    const res = await fetch('/get_questions');
    const data = await res.json();
    
    // If we got questions from session, use those
    if (data.questions && data.questions.length > 0) {
      questions = data.questions;
      console.log(`Loaded ${questions.length} questions from session`);
    } else {
      // Fallback to generating new questions via /api/get_question
      const fallbackRes = await fetch('/api/get_question');
      const fallbackData = await fallbackRes.json();
      questions = fallbackData.questions || [];
      console.log(`Generated ${questions.length} new questions as fallback`);
    }

    // Update UI
    qTotal.innerText = questions.length;
    current = 0;
    showQuestion();
  } catch (err) {
    console.error("Error loading questions:", err);
    questionText.innerText = "Error loading questions. Please try refreshing the page.";
  }
}


// New: Initialize or restore interview state and render preview
async function initializeInterviewState() {
  try {
    const res = await fetch('/get_questions');
    if (!res.ok) throw new Error('Failed to fetch questions');
    
    const data = await res.json();
    const serverQuestions = data.questions || [];
    const skills = data.skills || [];

    // Update question preview list if it exists
    const list = document.getElementById('question-list');
    if (list && Array.isArray(serverQuestions)) {
      // Show both skills and questions in the preview
      list.innerHTML = `
        ${skills.length ? `<div class="skills-preview" style="margin-bottom:1rem">
          <strong>Skills Identified:</strong>
          <p style="color:#4caf50">${skills.join(', ')}</p>
        </div>` : ''}
        <strong>Questions:</strong>
        ${serverQuestions.map(q => `<li>${q}</li>`).join('')}
      `;
    }

    // Initialize the interview state
    if (Array.isArray(serverQuestions) && serverQuestions.length) {
      questions = serverQuestions;
      if (qTotal) qTotal.innerText = questions.length;
      current = 0;
      showQuestion();
      console.log(`Interview initialized with ${questions.length} questions based on ${skills.length} skills`);
    } else {
      console.log('No pre-generated questions found, will fall back to generation');
      loadQuestions(); // Fallback to question generation
    }
  } catch (err) {
    console.error('Error initializing interview:', err);
    // Fallback to question generation on error
    loadQuestions();
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
// (event listener attached after DOM ready)
// ======================================================

// ======================================================
// 🎬 INITIALIZATION AND EVENT LISTENERS
// ======================================================

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  // Get UI elements after DOM is ready
  cameraEl = document.getElementById('camera');
  startBtn = document.getElementById('startTranscriptionBtn');
  stopBtn = document.getElementById('stopTranscriptionBtn');
  nextBtn = document.getElementById('nextBtn');
  
  // Initialize other UI element references
  questionText = document.getElementById('question-text');
  transcriptDiv = document.getElementById('transcript');
  feedbackDiv = document.getElementById('feedback');
  qIndex = document.getElementById('qIndex');
  qTotal = document.getElementById('qTotal');

  if (!startBtn || !stopBtn || !nextBtn) {
    console.error('Required UI elements not found. Check IDs in HTML.');
    return;
  }

  // Attach event listeners
  startBtn.addEventListener('click', startRecording);
  stopBtn.addEventListener('click', stopRecording);
  nextBtn.addEventListener('click', () => {
    current++;
    showQuestion();
  });

  // Initialize camera and questions
  // Show loader while initializing (fetching/generating questions)
  const loader = document.getElementById('interviewLoader');
  if (loader) loader.style.display = 'flex';

  await initCamera();
  await initializeInterviewState();

  // Hide loader after initialization
  if (loader) loader.style.display = 'none';
  console.log('Interview page initialized successfully');
});
