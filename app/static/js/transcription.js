document.addEventListener("DOMContentLoaded", () => {
  const startBtn = document.getElementById("startTranscriptionBtn");
  const stopBtn = document.getElementById("stopTranscriptionBtn");
  const transcriptText = document.getElementById("transcriptText");

  if (!startBtn || !stopBtn) return;

  startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    transcriptText.textContent = "Listening...";
    await fetch("/start_transcription", { method: "POST" });
  });

  stopBtn.addEventListener("click", async () => {
    stopBtn.disabled = true;
    startBtn.disabled = false;
    const res = await fetch("/stop_transcription", { method: "POST" });
    const data = await res.json();
    transcriptText.textContent = data.transcript || "(No transcript)";
  });
});
