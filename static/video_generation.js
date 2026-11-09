const generateVideoBtn = document.getElementById("generateVideoBtn");
const videoPrompt = document.getElementById("videoPrompt");
const videoDuration = document.getElementById("videoDuration");
const videoGenerateStatus = document.getElementById("videoGenerateStatus");

if (generateVideoBtn) {
  generateVideoBtn.addEventListener("click", async () => {
    const text = videoPrompt.value.trim();
    const duration = Number(videoDuration.value || 8);
    if (!text) {
      videoGenerateStatus.textContent = "Введите описание для генерации.";
      return;
    }
    if (!Number.isInteger(duration) || duration < 1 || duration > 60) {
      videoGenerateStatus.textContent = "Длительность должна быть от 1 до 60 секунд.";
      return;
    }

    generateVideoBtn.disabled = true;
    videoGenerateStatus.textContent = "Создаю задачу...";
    try {
      const form = new FormData();
      form.append("text", text);
      form.append("duration_seconds", String(duration));
      const response = await fetch("/media/video/generate", { method: "POST", body: form });
      const job = await response.json();
      if (!response.ok) throw new Error(job.detail || "Не удалось запустить генерацию.");
      await pollVideoJob(job.id);
    } catch (error) {
      videoGenerateStatus.textContent = error.message || "Ошибка генерации.";
      generateVideoBtn.disabled = false;
    }
  });
}

async function pollVideoJob(jobId) {
  const deadline = Date.now() + 31 * 60 * 1000;
  while (Date.now() < deadline) {
    const response = await fetch(`/media/video/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "Ошибка проверки задачи.");
    videoGenerateStatus.textContent = job.message || `Статус: ${job.status}`;

    if (job.status === "completed") {
      const video = document.createElement("video");
      video.controls = true;
      video.playsInline = true;
      video.src = job.video_url;
      video.style.maxWidth = "100%";
      const link = document.createElement("a");
      link.href = job.video_url;
      link.download = `generated-${jobId}`;
      link.textContent = "Скачать видео";
      videoGenerateStatus.replaceChildren(document.createTextNode("Видео готово. "), link);
      videoGenerateStatus.appendChild(document.createElement("br"));
      videoGenerateStatus.appendChild(video);
      generateVideoBtn.disabled = false;
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "ComfyUI завершил задачу с ошибкой.");
    await new Promise(resolve => setTimeout(resolve, 2500));
  }
  throw new Error("Истекло время ожидания статуса. Проверьте ComfyUI.");
}
