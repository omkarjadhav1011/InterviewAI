// interview.js
// Handles camera preview, recording audio, sending to /api/stt and /api/evaluate, and TTS playback via /api/tts

const cameraEl = document.getElementById('camera');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const nextBtn = document.getElementById('nextBtn');
const questionText = document.getElementById('question-text');
const transcriptDiv = document.getElementById('transcript');
const feedbackDiv = document.getElementById('feedback');
const qIndex = document.getElementById('qIndex');
const qTotal = document.getElementById('qTotal');

let mediaRecorder;
let audioChunks = [];
let questions = [];
let current = 0;

async function initCamera(){
  try{
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    cameraEl.srcObject = stream;
    // prepare recorder using audio tracks
    const audioStream = new MediaStream(stream.getAudioTracks());
    mediaRecorder = new MediaRecorder(audioStream);
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = onRecordingStop;
  }catch(e){ console.error('Camera init failed', e); }
}

async function loadQuestions(){
  const res = await fetch('/api/get_question');
  const data = await res.json();
  questions = data.questions || [];
  qTotal.innerText = questions.length;
  current = 0;
  showQuestion();
}

function showQuestion(){
  if(current >= questions.length){
    window.location.href = '/results';
    return;
  }
  questionText.innerText = questions[current];
  qIndex.innerText = current+1;
  // TTS
  fetch('/api/tts', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text: questions[current]})})
    .then(r=>r.json()).then(d=>{
      // if audio_url provided, play it
      if(d.audio_url){
        const audio = new Audio(d.audio_url);
        audio.play();
      } else {
        // fallback to browser TTS
        const ut = new SpeechSynthesisUtterance(questions[current]);
        speechSynthesis.speak(ut);
      }
    });
}

function startRecording(){
  audioChunks = [];
  mediaRecorder.start();
  startBtn.disabled = true;
  stopBtn.disabled = false;
}

function stopRecording(){
  mediaRecorder.stop();
  startBtn.disabled = false;
  stopBtn.disabled = true;
}

async function onRecordingStop(){
  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  const form = new FormData();
  form.append('audio', blob, 'answer.webm');
  // send to STT
  const res = await fetch('/api/stt', { method: 'POST', body: form });
  const data = await res.json();
  const transcript = data.transcript || '';
  transcriptDiv.innerText = transcript;
  // evaluate with Gemini
  const evalRes = await fetch('/api/evaluate', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({question: questions[current], answer: transcript})});
  const evalData = await evalRes.json();
  feedbackDiv.innerText = JSON.stringify(evalData.result);
  current++;
}

startBtn.addEventListener('click', startRecording);
stopBtn.addEventListener('click', stopRecording);
nextBtn.addEventListener('click', showQuestion);

initCamera();
loadQuestions();
