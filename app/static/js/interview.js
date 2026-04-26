// ======================================================
// interview.js — state-machine driven recording + Q&A flow
// ======================================================

// ── Module state ──────────────────────────────────────
let interviewState       = 'loading';
let currentQuestionIndex = 0;
let totalQuestions       = 5;
let currentQuestion      = null;
let liveTranscript       = '';   // accumulates while recording
let finalTranscript      = '';   // locked after Stop
let mediaStream          = null;
let audioContext         = null;
let processor            = null;
let wsConnection         = null;
let ttsAudio             = null;

// STT mode (assemblyai | whisper)
let sttMode             = 'assemblyai';
let whisperInitialized  = false;

// Element refs (resolved at DOMContentLoaded)
let cameraEl, btnStart, btnStop, btnNext, typedAnswerInput;
let questionTextEl, transcriptEl, transcriptTextEl, feedbackDiv;
let qIndex, qTotal, sttModeSelect, whisperStatusEl;

const WHISPER_MSGS = {
  loading: 'Loading Whisper model…',
  downloading: 'Downloading model (first time only)…',
  ready: 'Whisper ready',
  transcribing: 'Transcribing…',
  error: 'Whisper unavailable — using Web Speech API fallback',
  'ready-fallback': 'Using Web Speech API fallback',
};

const TRANSCRIPT_PLACEHOLDER = 'Press the mic to begin recording…';

// ======================================================
// STATE MACHINE — single source of truth for UI control
// ======================================================
function setState(newState) {
  console.log(`[state] ${interviewState} → ${newState}`);
  interviewState = newState;

  const ui = {
    'loading':      { startVis: true,  startDis: true,  stopVis: false, stopDis: true,  nextDis: true,  msg: 'Loading question…' },
    'tts_playing':  { startVis: true,  startDis: true,  stopVis: false, stopDis: true,  nextDis: true,  msg: 'Listen to the question…' },
    'idle':         { startVis: true,  startDis: false, stopVis: false, stopDis: true,  nextDis: false, msg: TRANSCRIPT_PLACEHOLDER },
    'recording':    { startVis: false, startDis: true,  stopVis: true,  stopDis: false, nextDis: true,  msg: '● Recording — click stop when done' },
    'recorded':     { startVis: true,  startDis: false, stopVis: false, stopDis: true,  nextDis: false, msg: 'Answer captured — click Next to submit' },
    'submitting':   { startVis: true,  startDis: true,  stopVis: false, stopDis: true,  nextDis: true,  msg: 'Evaluating answer…' },
    'next_loading': { startVis: true,  startDis: true,  stopVis: false, stopDis: true,  nextDis: true,  msg: 'Loading next question…' },
    'complete':     { startVis: true,  startDis: true,  stopVis: false, stopDis: true,  nextDis: true,  msg: 'Interview complete — redirecting…' },
  };

  const cfg = ui[newState] || ui['idle'];
  if (btnStart) {
    btnStart.disabled      = cfg.startDis;
    btnStart.style.display = cfg.startVis ? '' : 'none';
  }
  if (btnStop) {
    btnStop.disabled       = cfg.stopDis;
    btnStop.style.display  = cfg.stopVis  ? '' : 'none';
  }
  if (btnNext) {
    btnNext.disabled = cfg.nextDis;
  }

  // Mic-wave animation reflects the actual recording state
  const wave = document.getElementById('iv-wave');
  if (wave) wave.classList.toggle('active', newState === 'recording');
}

// ======================================================
// HELPERS
// ======================================================
function updateTranscriptDisplay(text) {
  if (transcriptTextEl) transcriptTextEl.textContent = text || '';
}

function getTypedAnswer() {
  return typedAnswerInput ? typedAnswerInput.value : '';
}

function clearTypedAnswer() {
  if (typedAnswerInput) typedAnswerInput.value = '';
}

function getCurrentQuestionText() {
  return currentQuestion || (questionTextEl ? questionTextEl.textContent.trim() : '');
}

function showNotice(message, type = 'info') {
  if (!feedbackDiv) { console.warn('[notice]', message); return; }
  const colors = { info: '#00bcd4', warning: '#ffb84d', error: '#ff6b6b' };
  feedbackDiv.innerHTML = `
    <div style="padding:0.75rem 1rem;border-radius:8px;background:rgba(255,255,255,0.04);border-left:3px solid ${colors[type] || colors.info};color:#ddd;margin-top:0.5rem;">
      ${message}
    </div>`;
  clearTimeout(feedbackDiv._noticeTimer);
  feedbackDiv._noticeTimer = setTimeout(() => {
    if (feedbackDiv && feedbackDiv.firstElementChild &&
        feedbackDiv.firstElementChild.style &&
        feedbackDiv.firstElementChild.style.borderLeft) {
      feedbackDiv.innerHTML = '';
    }
  }, 6000);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data   = data;
    throw err;
  }
  return data;
}

function storeScore(index, result) {
  try {
    const scores = JSON.parse(sessionStorage.getItem('interviewScores') || '[]');
    scores[index] = result;
    sessionStorage.setItem('interviewScores', JSON.stringify(scores));
  } catch (_) { /* ignore */ }
}

function setNextLabel(text) {
  if (!btnNext) return;
  for (const node of btnNext.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
      node.textContent = text + ' ';
      return;
    }
  }
  btnNext.insertBefore(document.createTextNode(text + ' '), btnNext.firstChild);
}

// ======================================================
// CAMERA + MIC SETUP
// ======================================================
async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    if (cameraEl) cameraEl.srcObject = stream;
    mediaStream = stream;
  } catch (err) {
    console.error('Camera/mic init failed:', err);
    showNotice('Camera or microphone access denied. You can still type your answers.', 'warning');
  }
}

// ======================================================
// QUESTION LOADING
// ======================================================
async function loadQuestion(index) {
  setState(index === 0 ? 'loading' : 'next_loading');
  finalTranscript = '';
  liveTranscript  = '';
  clearTypedAnswer();
  updateTranscriptDisplay(TRANSCRIPT_PLACEHOLDER);
  if (feedbackDiv) feedbackDiv.innerHTML = '';

  try {
    const data = await fetchJSON(`/get_questions?question=${index}`);
    if (!data.currentQuestion) throw new Error('No question received from server');

    currentQuestion = data.currentQuestion;
    totalQuestions  = data.totalQuestions || totalQuestions;
    renderQuestion(data);

    await playTTS(currentQuestion);
    setState('idle');
    updateTranscriptDisplay(TRANSCRIPT_PLACEHOLDER);
  } catch (err) {
    console.error('[loadQuestion]', err);
    if (questionTextEl) questionTextEl.textContent = 'Error loading question. Please refresh the page.';
    showNotice('Failed to load question — please refresh.', 'error');
    // Stay in loading; do not let user submit against an unknown question.
  }
}

function renderQuestion(data) {
  if (questionTextEl) questionTextEl.textContent = data.currentQuestion;
  if (qTotal)         qTotal.innerText = data.totalQuestions || totalQuestions;
  if (qIndex && data.progress) qIndex.innerText = data.progress.current;

  const tag = document.getElementById('iv-q-tag');
  if (tag) {
    const n = (data.progress && data.progress.current) || (currentQuestionIndex + 1);
    tag.textContent = `Question ${String(n).padStart(2, '0')}`;
  }

  const previewDiv = document.getElementById('question-list');
  if (previewDiv && data.progress) {
    previewDiv.innerHTML = `
      <div class="progress-bar" style="width:100%;height:4px;background:rgba(255,255,255,0.1);margin-bottom:1rem;">
        <div style="width:${data.progress.completed}%;height:100%;background:#00bcd4;transition:width 0.3s ease;"></div>
      </div>
      <div style="color:#00bcd4;margin-bottom:1rem;">
        Question ${data.progress.current} of ${data.progress.total}
      </div>
      <div style="color:#ddd;">
        Current Question:<br><strong>${data.currentQuestion}</strong>
      </div>`;
  }

  setNextLabel(data.isLastQuestion ? 'Finish' : 'Next');
}

// ======================================================
// TTS — always resolves, never blocks the flow
// ======================================================
async function playTTS(text) {
  return new Promise((resolve) => {
    // Stop anything already playing
    if (ttsAudio) { try { ttsAudio.pause(); } catch (_) {} ttsAudio = null; }
    if (window.speechSynthesis) { try { window.speechSynthesis.cancel(); } catch (_) {} }

    setState('tts_playing');

    // Backend returns JSON { audio_url, fallback }
    fetchJSON('/api/tts', { method: 'POST', body: JSON.stringify({ text }) })
      .then((d) => {
        if (d && d.audio_url) {
          ttsAudio = new Audio(d.audio_url);
          ttsAudio.onended = () => { ttsAudio = null; resolve(); };
          ttsAudio.onerror = () => { ttsAudio = null; tryBrowserTTS(text, resolve); };
          ttsAudio.play().catch(() => tryBrowserTTS(text, resolve));
        } else {
          tryBrowserTTS(text, resolve);
        }
      })
      .catch(() => tryBrowserTTS(text, resolve));
  });
}

function tryBrowserTTS(text, resolve) {
  if (!window.speechSynthesis) { resolve(); return; }
  try {
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 0.95;

    const safety = setTimeout(() => {
      try { window.speechSynthesis.cancel(); } catch (_) {}
      resolve();
    }, Math.max(8000, text.length * 65));

    utter.onend   = () => { clearTimeout(safety); resolve(); };
    utter.onerror = () => { clearTimeout(safety); resolve(); };
    window.speechSynthesis.speak(utter);
  } catch (_) {
    resolve();
  }
}

// ======================================================
// RECORDING — start
// ======================================================
async function startRecording() {
  if (interviewState !== 'idle') return;   // guard against double-start
  setState('recording');
  liveTranscript = '';
  updateTranscriptDisplay('Listening…');

  try {
    if (!mediaStream || !mediaStream.active) {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }

    // Whisper (offline) path
    if (sttMode === 'whisper') {
      if (!window.WhisperSTT) throw new Error('Whisper not available');
      await window.WhisperSTT.startRecording(mediaStream);
      updateTranscriptDisplay('Recording… (click Stop to transcribe)');
      return;
    }

    // AssemblyAI path — fetch ws_url (token embedded), open WebSocket
    const tokenData = await fetchJSON('/start_transcription', { method: 'POST' });
    if (!tokenData.ws_url) throw new Error(tokenData.error || 'No WebSocket URL received');

    wsConnection = new WebSocket(tokenData.ws_url);

    wsConnection.onopen = () => startAudioStreaming();

    wsConnection.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }

      // AssemblyAI v3 Universal-Streaming format
      if (msg.type === 'Turn' && msg.transcript) {
        if (msg.end_of_turn) {
          liveTranscript += msg.transcript + ' ';
          updateTranscriptDisplay(liveTranscript.trim());
          // Best-effort backup to server
          fetch('/update_transcript', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: msg.transcript }),
          }).catch(() => {});
        } else {
          updateTranscriptDisplay((liveTranscript + msg.transcript).trim());
        }
      } else if (msg.type === 'Begin') {
        console.log('AssemblyAI session started:', msg.id);
      } else if (msg.type === 'Termination') {
        console.log('AssemblyAI session ended:', msg.audio_duration_seconds, 's');
      }
    };

    wsConnection.onerror = () => {
      handleRecordingError('Transcription error — your typed answer can still be used.');
    };

    wsConnection.onclose = (event) => {
      // 1000 = we closed it intentionally in stopRecording()
      if (interviewState === 'recording' && event.code !== 1000) {
        handleRecordingError('Transcription disconnected — recording stopped.');
      }
    };
  } catch (err) {
    if (err && (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError')) {
      handleRecordingError('Microphone access denied. Please type your answer below.');
    } else {
      handleRecordingError('Could not start recording: ' + (err && err.message ? err.message : err));
    }
  }
}

// ======================================================
// PCM16 audio streaming to WebSocket
// ======================================================
function startAudioStreaming() {
  try {
    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(mediaStream);
    processor    = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
      if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) return;
      const f32 = e.inputBuffer.getChannelData(0);
      wsConnection.send(float32ToPCM16(f32));
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  } catch (err) {
    console.error('Audio streaming init failed:', err);
    handleRecordingError('Audio capture failed.');
  }
}

function float32ToPCM16(f32) {
  const buf  = new ArrayBuffer(f32.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buf;
}

// ======================================================
// RECORDING — stop & lock transcript
// ======================================================
async function stopRecording() {
  if (interviewState !== 'recording') return;   // guard against double-stop

  // Whisper path — transcription happens locally on stop
  if (sttMode === 'whisper') {
    setState('submitting');   // brief "working" indicator while Whisper decodes
    if (whisperStatusEl) {
      whisperStatusEl.textContent = WHISPER_MSGS.transcribing;
      whisperStatusEl.style.display = 'inline';
    }
    try {
      const text = (await (window.WhisperSTT && window.WhisperSTT.stopRecording())) || '';
      finalTranscript = text.trim();
    } catch (err) {
      console.error('Whisper stop:', err);
      finalTranscript = '';
    }
    if (whisperStatusEl) {
      whisperStatusEl.textContent = WHISPER_MSGS.ready;
      whisperStatusEl.style.display = 'none';
    }
    updateTranscriptDisplay(finalTranscript || '(no speech detected — type your answer below)');
    setState('recorded');
    return;
  }

  // AssemblyAI path
  if (processor)    { try { processor.disconnect(); }   catch (_) {} processor = null; }
  if (audioContext) { try { audioContext.close(); }     catch (_) {} audioContext = null; }

  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    try { wsConnection.send(JSON.stringify({ type: 'Terminate' })); } catch (_) {}
    try { wsConnection.close(1000, 'User stopped recording'); }       catch (_) {}
  }
  wsConnection = null;

  // Server-side transcript is more authoritative; fall back to client-accumulated.
  try {
    const r = await fetchJSON('/stop_transcription', { method: 'POST' });
    const serverText = (r && r.transcript) ? r.transcript.trim() : '';
    finalTranscript = serverText || liveTranscript.trim();
  } catch (_) {
    finalTranscript = liveTranscript.trim();
  }

  updateTranscriptDisplay(finalTranscript || '(no speech detected — type your answer below)');
  setState('recorded');
}

// ======================================================
// Recovery from any recording-related failure
// ======================================================
function handleRecordingError(message) {
  if (processor)    { try { processor.disconnect(); } catch (_) {} processor = null; }
  if (audioContext) { try { audioContext.close(); }   catch (_) {} audioContext = null; }
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    try { wsConnection.close(1000, 'error cleanup'); } catch (_) {}
  }
  wsConnection    = null;
  liveTranscript  = '';
  finalTranscript = '';
  updateTranscriptDisplay(TRANSCRIPT_PLACEHOLDER);
  setState('idle');
  showNotice(message, 'warning');
}

// ======================================================
// SUBMIT + ADVANCE  (Next button = submit answer & load next)
// ======================================================
async function submitAndAdvance() {
  // Allow submit from 'idle' (typed-only) or 'recorded'
  if (interviewState !== 'idle' && interviewState !== 'recorded') return;

  const voice = (finalTranscript || '').trim();
  const typed = getTypedAnswer().trim();

  if (!voice && !typed) {
    showNotice('Please record or type an answer before continuing.', 'warning');
    return;
  }

  const previousState = interviewState;
  setState('submitting');

  if (feedbackDiv) {
    feedbackDiv.innerHTML = `
      <div style="text-align:center;padding:1rem;">
        <div style="color:#00bcd4;margin-bottom:0.5rem;">Evaluating your answer…</div>
        <div style="width:40px;height:40px;border:3px solid #00bcd4;border-top-color:transparent;border-radius:50%;margin:0 auto;animation:spin 1s linear infinite;"></div>
      </div>`;
  }

  try {
    const data = await fetchJSON('/api/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        question:       getCurrentQuestionText(),
        answer:         voice,
        typed_answer:   typed,
        questionNumber: currentQuestionIndex,
      }),
    });

    storeScore(currentQuestionIndex, data.result);
    renderEvaluation(data.result);

    const isLast = !!data.is_last_question || (currentQuestionIndex >= totalQuestions - 1);
    if (isLast) {
      setState('complete');
      const redirect = data.redirect || (data.result && data.result.redirect) || '/results';
      setTimeout(() => { window.location.href = redirect; }, 2000);
      return;
    }

    currentQuestionIndex++;
    await loadQuestion(currentQuestionIndex);
  } catch (err) {
    console.error('[submitAndAdvance]', err);
    showNotice('Submission failed — please try again.', 'error');
    // Preserve the captured answer; let user retry.
    setState(previousState);
  }
}

function renderEvaluation(result) {
  if (!result || !feedbackDiv) return;
  feedbackDiv.innerHTML = `
    <div style="padding:1rem;background:rgba(0,188,212,0.1);border-radius:8px;">
      ${result.summary ? `
        <div style="margin-bottom:0.5rem;">
          <strong style="color:#00bcd4;">Summary:</strong>
          <div style="color:#ddd;margin-top:0.25rem;">${result.summary}</div>
        </div>` : ''}
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:0.75rem 0;">
        <div><div style="color:#00bcd4;">Confidence</div><div style="font-size:1.25rem;">${result.confidence ?? '—'}%</div></div>
        <div><div style="color:#00bcd4;">Technical</div><div style="font-size:1.25rem;">${result.technical ?? '—'}%</div></div>
        <div><div style="color:#00bcd4;">Communication</div><div style="font-size:1.25rem;">${result.communication ?? '—'}%</div></div>
      </div>
      ${result.feedback ? `
        <div style="margin-top:0.5rem;">
          <strong style="color:#00bcd4;">Feedback:</strong>
          <div style="color:#ddd;margin-top:0.25rem;">${result.feedback}</div>
        </div>` : ''}
    </div>`;
}

// ======================================================
// INIT
// ======================================================
document.addEventListener('DOMContentLoaded', async () => {
  cameraEl         = document.getElementById('camera');
  btnStart         = document.getElementById('startTranscriptionBtn');
  btnStop          = document.getElementById('stopTranscriptionBtn');
  btnNext          = document.getElementById('nextBtn');
  typedAnswerInput = document.getElementById('typedAnswerInput');
  questionTextEl   = document.getElementById('question-text');
  transcriptEl     = document.getElementById('transcript');
  transcriptTextEl = document.getElementById('transcriptText');
  feedbackDiv      = document.getElementById('feedback');
  qIndex           = document.getElementById('qIndex');
  qTotal           = document.getElementById('qTotal');
  sttModeSelect    = document.getElementById('sttModeSelect');
  whisperStatusEl  = document.getElementById('whisperStatusEl');

  if (!btnStart || !btnStop || !btnNext) {
    console.error('Required UI elements not found. Check IDs in HTML.');
    return;
  }

  // STT mode selector
  if (sttModeSelect) {
    sttModeSelect.addEventListener('change', async () => {
      sttMode = sttModeSelect.value;
      if (sttMode === 'whisper' && !whisperInitialized && window.WhisperSTT) {
        whisperInitialized = true;
        await window.WhisperSTT.initWhisper((state) => {
          if (!whisperStatusEl) return;
          whisperStatusEl.textContent   = WHISPER_MSGS[state] || '';
          whisperStatusEl.style.display = state === 'ready' ? 'none' : 'inline';
        });
      }
    });
  }

  btnStart.addEventListener('click', startRecording);
  btnStop .addEventListener('click', stopRecording);
  btnNext .addEventListener('click', submitAndAdvance);

  // Spinner keyframes (shared across this view)
  const style = document.createElement('style');
  style.textContent = '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
  document.head.appendChild(style);

  // Establish initial UI state before any async work
  setState('loading');

  const loader = document.getElementById('interviewLoader');
  if (loader) loader.style.display = 'flex';

  try {
    await initCamera();
    await loadQuestion(0);
  } catch (err) {
    console.error('Interview init error:', err);
    if (questionTextEl) questionTextEl.textContent = 'Error initializing interview. Please refresh the page.';
    showNotice('Failed to initialize interview.', 'error');
  } finally {
    if (loader) loader.style.display = 'none';
  }
});
