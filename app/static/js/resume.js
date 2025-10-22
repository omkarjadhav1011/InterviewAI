// resume.js
// Handles resume upload, shows a progress bar, and displays extracted keywords.
// TODO: improve error handling and large file uploads
document.getElementById('resumeForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fileInput = document.getElementById('resumeFile');
  if(!fileInput.files.length) return alert('Select a PDF');
  const file = fileInput.files[0];
  const form = new FormData();
  form.append('resume', file);

  document.getElementById('progress').style.display = 'block';
  document.getElementById('progressText').innerText = 'Uploading...';

  const res = await fetch('/upload', { method: 'POST', body: form });
  if(!res.ok){
    document.getElementById('progressText').innerText = 'Error uploading';
    return;
  }
  document.getElementById('progressText').innerText = 'Parsing...';
  const data = await res.json();
  document.getElementById('progressText').innerText = 'Done';
  document.getElementById('keywords').innerText = 'Keywords: ' + (data.keywords || []).join(', ');
  // show Start Interview button dynamically
  const btn = document.createElement('a');
  btn.href = '/interview';
  btn.innerText = 'Start Interview';
  document.getElementById('keywords').appendChild(document.createElement('br'));
  document.getElementById('keywords').appendChild(btn);
});
