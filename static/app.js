const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const fileList = document.getElementById("fileList");
const chatHistory = document.getElementById("chatHistory");

const askBtn = document.getElementById("askBtn");
const questionInput = document.getElementById("questionInput");
const answerOutput = document.getElementById("answerOutput");
const speakBtn = document.getElementById("speakBtn");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");

const calcBtn = document.getElementById("calcBtn");
const calcInput = document.getElementById("calcInput");
const calcOutput = document.getElementById("calcOutput");

const videoSelect = document.getElementById("videoSelect");
const analyzeVideoBtn = document.getElementById("analyzeVideoBtn");
const videoOutput = document.getElementById("videoOutput");
const videoQuestion = document.getElementById("videoQuestion");
const frameCountInput = document.getElementById("frameCountInput");
const includeVideoAudio = document.getElementById("includeVideoAudio");

const generateVideoBtn = document.getElementById("generateVideoBtn");
const videoPrompt = document.getElementById("videoPrompt");
const videoDuration = document.getElementById("videoDuration");
const videoGenerateStatus = document.getElementById("videoGenerateStatus");

function renderHistory(items) {
  chatHistory.replaceChildren();

  if (!items.length) {
    chatHistory.textContent = "История пуста.";
    return;
  }

  for (const item of items) {
    const entry = document.createElement("div");
    entry.className = "chat-entry";

    const label = document.createElement("strong");
    label.textContent = item.role === "user" ? "Вы: " : "AI: ";

    const content = document.createElement("div");
    content.textContent = item.content;

    entry.append(label, content);
    chatHistory.appendChild(entry);
  }
}

async function refreshFiles() {
  const res = await fetch("/files");
  const data = await res.json();
  const files = data.files || [];

  fileList.textContent = files.length ? files.map(f => `• ${f}`).join("\n") : "Файлы не загружены.";
  videoSelect.replaceChildren();

  for (const name of files.filter(file => /\.(mp4|mov|mkv|webm|avi)$/i.test(file))) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    videoSelect.appendChild(option);
  }
}

async function refreshHistory() {
  const res = await fetch("/history");
  const data = await res.json();
  renderHistory(data.history || []);
}

uploadBtn.addEventListener("click", async () => {
  const files = fileInput.files;
  if (!files || files.length === 0) {
    uploadStatus.textContent = "Выберите хотя бы один файл.";
    return;
  }

  uploadStatus.textContent = "Загрузка...";
  for (const file of files) {
    const form = new FormData();
    form.append("file", file);
    await fetch("/upload", { method: "POST", body: form });
  }

  uploadStatus.textContent = "Файлы загружены.";
  await refreshFiles();
});

askBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    answerOutput.textContent = "Введите вопрос.";
    return;
  }

  const files = (await fetch("/files").then(r => r.json())).files || [];
  const form = new FormData();
  form.append("question", question);
  form.append("selected_files", files.join(","));
  form.append("wiki_on", document.getElementById("wikiCheck").checked ? "on" : "off");
  form.append("image_on", document.getElementById("imageCheck").checked ? "on" : "off");
  form.append("audio_on", document.getElementById("audioCheck").checked ? "on" : "off");

  answerOutput.textContent = "Обрабатываю...";
  const res = await fetch("/ask", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    answerOutput.textContent = data.answer || "Нет ответа.";
    await refreshHistory();
  } else {
    answerOutput.textContent = data.detail || "Ошибка.";
  }
});

calcBtn.addEventListener("click", async () => {
  const expr = calcInput.value.trim();
  if (!expr) {
    calcOutput.textContent = "Введите выражение.";
    return;
  }

  const form = new FormData();
  form.append("expr", expr);
  const res = await fetch("/calc", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    calcOutput.textContent = String(data.result);
  } else {
    calcOutput.textContent = data.detail || "Ошибка вычисления.";
  }
});

clearHistoryBtn.addEventListener("click", async () => {
  await fetch("/history/clear", { method: "POST" });
  await refreshHistory();
});

speakBtn.addEventListener("click", async () => {
  const text = answerOutput.textContent.trim();
  if (!text) return;

  const form = new FormData();
  form.append("text", text);
  const res = await fetch("/media/tts", { method: "POST", body: form });

  if (!res.ok) {
    const data = await res.json();
    answerOutput.textContent = data.detail || "Ошибка озвучки.";
    return;
  }

  const audioBlob = await res.blob();
  const url = URL.createObjectURL(audioBlob);
  const audio = new Audio(url);
  audio.play();
});

analyzeVideoBtn.addEventListener("click", async () => {
  const filename = videoSelect.value;
  const question = videoQuestion.value.trim() || "Что происходит в этом видео?";
  const frameCount = Number(frameCountInput.value || 6);
  const includeAudio = includeVideoAudio.checked;

  if (!filename) {
    videoOutput.textContent = "Сначала загрузите видеофайл.";
    return;
  }

  const form = new FormData();
  form.append("filename", filename);
  form.append("question", question);
  form.append("frame_count", String(frameCount));
  form.append("include_audio", includeAudio ? "true" : "false");

  videoOutput.textContent = "Анализирую видео...";
  const res = await fetch("/media/video/analyze", { method: "POST", body: form });
  const data = await res.json();

  if (!res.ok) {
    videoOutput.textContent = data.detail || "Ошибка анализа.";
    return;
  }

  const transcript = data.transcript ? `\n\nРечь:\n${data.transcript}` : "";
  const timestamps = data.sampled_timestamps?.length ? `\n\nКадры в секундах: ${data.sampled_timestamps.join(", ")}` : "";
  videoOutput.textContent = `${data.answer}${transcript}${timestamps}`;
});

generateVideoBtn.addEventListener("click", async () => {
  const text = videoPrompt.value.trim();
  const duration = Number(videoDuration.value || 8);

  if (!text) {
    videoGenerateStatus.textContent = "Введите описание для генерации.";
    return;
  }

  if (!Number.isFinite(duration) || duration < 1 || duration > 600) {
    videoGenerateStatus.textContent = "Длительность должна быть от 1 до 600 секунд.";
    return;
  }

  const form = new FormData();
  form.append("text", text);
  form.append("duration_seconds", String(duration));

  videoGenerateStatus.textContent = "Отправляю задачу в ComfyUI...";
  const res = await fetch("/media/video/generate", { method: "POST", body: form });
  const data = await res.json();

  if (!res.ok) {
    videoGenerateStatus.textContent = data.detail || "Ошибка генерации.";
    return;
  }

  if (data.video_path) {
    videoGenerateStatus.textContent = `Видео создано: ${data.video_path}`;
    const link = document.createElement("a");
    link.href = `/${data.video_path.replace(/\\/g, "/")}`;
    link.download = "generated-video";
    link.textContent = "Скачать";
    videoGenerateStatus.appendChild(document.createElement("br"));
    videoGenerateStatus.appendChild(link);
  } else {
    videoGenerateStatus.textContent = `Статус: ${data.status || "в обработке"}`;
  }
});

refreshFiles();
refreshHistory();
