document.getElementById('resumeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('resumeFile');
  const progress = document.getElementById('progress');
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  // Keep skills container id="keywords" in the template
  const skillsContainer = document.getElementById('keywords');

  // Reset UI
  progress.style.display = 'block';
  progressBar.style.width = '0%';
  progressText.innerText = '';
  skillsContainer.innerHTML = '';

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
  let res;
  try {
    // Post to the current path so the code works regardless of blueprint prefix.
    res = await fetch(window.location.pathname || '/upload', { method: 'POST', body: form });
  } catch (err) {
    simulateProgress(100, '❌ Network error. Please try again.');
    progressBar.style.background = '#e74c3c';
    console.error('Upload network error:', err);
    return;
  }

  if (!res.ok) {
    // Try to read JSON error message, otherwise show generic
    let msg = 'Upload failed. Please try again.';
    try {
      const errJson = await res.json();
      if (errJson && errJson.error) msg = errJson.error;
    } catch (e) { /* ignore */ }
    simulateProgress(100, `❌ ${msg}`);
    progressBar.style.background = '#e74c3c';
    return;
  }

  simulateProgress(60, 'Parsing your resume...');
  let data;
  try {
    data = await res.json();
  } catch (err) {
    simulateProgress(100, '❌ Server returned invalid JSON.');
    progressBar.style.background = '#e74c3c';
    console.error('JSON parse error:', err);
    return;
  }

  simulateProgress(100, '✅ Done! Skills extracted.');
  progressBar.style.background = '#2ecc71';

  // Display skills: prefer `skills`, fall back to `keywords`.
  // Normalize to array of strings.
  const skills = data.skills || data.keywords || [];
  if (Array.isArray(skills) && skills.length) {
    skillsContainer.innerHTML = `
      <h3>Extracted Skills</h3>
      <div class="keyword-list">
        ${skills.map(skill => `<span class="keyword">${skill}</span>`).join('')}
      </div>
    `;
  } else if (typeof skills === 'string' && skills.trim()) {
    skillsContainer.innerHTML = `<h3>Extracted Skills</h3><p>${skills}</p>`;
  } else {
    skillsContainer.innerHTML = '<p>No skills found.</p>';
  }

  // Create Start Interview button dynamically
  // Use relative link to interview page
  const btn = document.createElement('a');
  btn.href = '/interview';
  btn.className = 'start-btn';
  btn.innerText = '🎤 Start Interview';
  skillsContainer.appendChild(btn);
});
