// // resume.js
// // Handles resume upload, shows a progress bar, and displays extracted keywords.
// // TODO: improve error handling and large file uploads
// document.getElementById('resumeForm').addEventListener('submit', async (e)=>{
//   e.preventDefault();
//   const fileInput = document.getElementById('resumeFile');
//   if(!fileInput.files.length) return alert('Select a PDF');
//   const file = fileInput.files[0];
//   const form = new FormData();
//   form.append('resume', file);

//   document.getElementById('progress').style.display = 'block';
//   document.getElementById('progressText').innerText = 'Uploading...';

//   const res = await fetch('/upload', { method: 'POST', body: form });
//   if(!res.ok){
//     document.getElementById('progressText').innerText = 'Error uploading';
//     return;
//   }
//   document.getElementById('progressText').innerText = 'Parsing...';
//   const data = await res.json();
//   document.getElementById('progressText').innerText = 'Done';
//   document.getElementById('keywords').innerText = 'Keywords: ' + (data.keywords || []).join(', ');
//   // show Start Interview button dynamically
//   const btn = document.createElement('a');
//   btn.href = '/interview';
//   btn.innerText = 'Start Interview';
//   document.getElementById('keywords').appendChild(document.createElement('br'));
//   document.getElementById('keywords').appendChild(btn);
// });

// resume.js
// Handles resume upload, shows a progress bar, and displays extracted keywords with animations.

document.getElementById('resumeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('resumeFile');
  const progress = document.getElementById('progress');
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  const keywordsContainer = document.getElementById('keywords');

  // Reset UI
  progress.style.display = 'block';
  progressBar.style.width = '0%';
  progressText.innerText = '';
  keywordsContainer.innerHTML = '';

  if (!fileInput.files.length) return alert('Please select a PDF file first.');

  const file = fileInput.files[0];
  const form = new FormData();
  form.append('resume', file);

  // Simulate progress visually
  function simulateProgress(value, text) {
    progressBar.style.width = `${value}%`;
    progressText.innerText = text;
  }

  simulateProgress(20, 'Uploading...');
  const res = await fetch('/upload', { method: 'POST', body: form });

  if (!res.ok) {
    simulateProgress(100, '❌ Upload failed. Please try again.');
    progressBar.style.background = '#e74c3c';
    return;
  }

  simulateProgress(60, 'Parsing your resume...');
  const data = await res.json();

  simulateProgress(100, '✅ Done! Keywords extracted.');
  progressBar.style.background = '#2ecc71';

  // Display keywords nicely
  const keywords = data.keywords || [];
  if (keywords.length) {
    keywordsContainer.innerHTML = `
      <h3>Extracted Keywords</h3>
      <div class="keyword-list">
        ${keywords.map(k => `<span class="keyword">${k}</span>`).join('')}
      </div>
    `;
  } else {
    keywordsContainer.innerHTML = '<p>No keywords found.</p>';
  }

  // Create Start Interview button dynamically
  const btn = document.createElement('a');
  btn.href = '/interview';
  btn.className = 'start-btn';
  btn.innerText = '🎤 Start Interview';
  keywordsContainer.appendChild(btn);
});
