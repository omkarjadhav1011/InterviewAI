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
let currentQuestion = null;
let questionNumber = 0;
let totalQuestions = 5;
let mediaStream = null;
let websocket = null;
let audioContext = null;
let processor = null;
let isRecording = false;
let evaluationInProgress = false;

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
// 🧠 LOAD CURRENT QUESTION
// ======================================================
async function loadCurrentQuestion() {
    const loader = document.getElementById('interviewLoader');
    if (loader) loader.style.display = 'flex';

    try {
        const res = await fetch(`/get_questions?question=${questionNumber}`);
        const data = await res.json();
        
        if (data.currentQuestion) {
            currentQuestion = data.currentQuestion;
            totalQuestions = data.totalQuestions;
            
            // Update progress
            qTotal.innerText = totalQuestions;
            qIndex.innerText = data.progress.current;
            
            // Show the question
            showQuestion();
            
            // Update preview section if exists
            const previewDiv = document.getElementById('question-list');
            if (previewDiv) {
                previewDiv.innerHTML = `
                    <div class="progress-bar" style="width: 100%; height: 4px; background: rgba(255,255,255,0.1); margin-bottom: 1rem;">
                        <div style="width: ${data.progress.completed}%; height: 100%; background: #00bcd4; transition: width 0.3s ease;"></div>
                    </div>
                    <div style="color: #00bcd4; margin-bottom: 1rem;">
                        Question ${data.progress.current} of ${data.progress.total}
                    </div>
                    <div style="color: #ddd;">
                        Current Question:<br>
                        <strong>${data.currentQuestion}</strong>
                    </div>
                `;
            }
            
            // Handle last question state
            nextBtn.textContent = data.isLastQuestion ? '➡ Finish Interview' : '➡ Next Question';
            
        } else {
            throw new Error('No question received from server');
        }
    } catch (err) {
        console.error("Error loading question:", err);
        questionText.innerText = "Error loading question. Please try refreshing the page.";
    } finally {
        if (loader) loader.style.display = 'none';
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
    if (!currentQuestion) {
        console.error('No current question to display');
        return;
    }

    // Reset UI state
    transcriptDiv.textContent = "Press start to begin recording...";
    feedbackDiv.textContent = "";
    startBtn.disabled = false;
    stopBtn.disabled = true;
    nextBtn.disabled = true;

    // Update question text
    questionText.innerText = currentQuestion;

    // Play question via backend TTS or fallback
    fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: currentQuestion })
    })
        .then(r => r.json())
        .then(d => {
            if (d.audio_url) {
                const audio = new Audio(d.audio_url);
                audio.play();
            } else {
                const utterance = new SpeechSynthesisUtterance(currentQuestion);
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
    if (!isRecording || evaluationInProgress) return;
    evaluationInProgress = true;

    startBtn.disabled = true;
    stopBtn.disabled = true;
    nextBtn.disabled = true;
    
    isRecording = false;

    if (processor) processor.disconnect();
    if (audioContext) audioContext.close();
    if (websocket) websocket.close();

    try {
        await fetch('/stop_transcription', { method: 'POST' });
        console.log("✅ Streaming session closed");
    } catch (err) {
        console.error("Error stopping transcription:", err);
    }

    // Show evaluation in progress
    feedbackDiv.innerHTML = `
        <div style="text-align: center; padding: 1rem;">
            <div style="color: #00bcd4; margin-bottom: 0.5rem;">Evaluating your answer...</div>
            <div style="width: 40px; height: 40px; border: 3px solid #00bcd4; border-top-color: transparent; border-radius: 50%; margin: 0 auto; animation: spin 1s linear infinite;"></div>
        </div>
    `;

    // Evaluate answer with Gemini
    const transcript = transcriptDiv.textContent;
    if (transcript && transcript.length > 0) {
        try {
            const evalRes = await fetch('/api/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: currentQuestion,
                    answer: transcript,
                    questionNumber: questionNumber
                })
            });
            const evalData = await evalRes.json();
            
            // Format and display feedback
            if (evalData.result) {
                const result = evalData.result;
                feedbackDiv.innerHTML = `
                    <div style="padding: 1rem; background: rgba(0,188,212,0.1); border-radius: 8px;">
                        <div style="margin-bottom: 0.5rem;">
                            <strong style="color: #00bcd4;">Evaluation Summary:</strong>
                            <div style="color: #ddd; margin-top: 0.5rem;">${result.summary}</div>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1rem 0;">
                            <div>
                                <div style="color: #00bcd4;">Confidence</div>
                                <div style="font-size: 1.25rem;">${result.confidence}%</div>
                            </div>
                            <div>
                                <div style="color: #00bcd4;">Technical</div>
                                <div style="font-size: 1.25rem;">${result.technical}%</div>
                            </div>
                            <div>
                                <div style="color: #00bcd4;">Communication</div>
                                <div style="font-size: 1.25rem;">${result.communication}%</div>
                            </div>
                        </div>
                        ${result.feedback ? `
                            <div style="margin-top: 0.5rem;">
                                <strong style="color: #00bcd4;">Feedback:</strong>
                                <div style="color: #ddd; margin-top: 0.25rem;">${result.feedback}</div>
                            </div>
                        ` : ''}
                    </div>
                `;

                // If we got a redirect URL, this was the last question
                if (result.redirect) {
                    setTimeout(() => {
                        window.location.href = result.redirect;
                    }, 2000);
                    return;
                }
            } else {
                feedbackDiv.innerText = "Evaluation complete!";
            }
            
            // Enable next question button
            nextBtn.disabled = false;
            startBtn.disabled = false;
            
        } catch (err) {
            feedbackDiv.innerText = "Error evaluating answer.";
            console.error("Evaluation error:", err);
            startBtn.disabled = false;
        }
    }
    
    evaluationInProgress = false;
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
    nextBtn.addEventListener('click', async () => {
        if (evaluationInProgress) return;
        
        questionNumber++;
        await loadCurrentQuestion();
        
        // Reset UI state for next question
        startBtn.disabled = false;
        stopBtn.disabled = true;
        nextBtn.disabled = true;
    });

    // Add some CSS for the evaluation spinner
    const style = document.createElement('style');
    style.textContent = `
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);

    // Initialize camera and first question
    const loader = document.getElementById('interviewLoader');
    if (loader) loader.style.display = 'flex';

    try {
        await initCamera();
        await loadCurrentQuestion(); // Load first question
        
        console.log('Interview page initialized successfully');
    } catch (error) {
        console.error('Error initializing interview:', error);
        questionText.innerText = 'Error initializing interview. Please refresh the page.';
    } finally {
        if (loader) loader.style.display = 'none';
    }
});
