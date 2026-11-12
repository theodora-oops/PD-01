// Workspace: tab input, unggah dokumen, dan pemanggilan analisis ke server Python.
const $ = (id) => document.getElementById(id);
const tabs = document.querySelectorAll("[data-mode]");
const textarea = $("requirement");
const titleInput = $("project-title");
const startButton = $("start-analysis");
const SUPPORTED = [".pdf", ".docx"];
const MAX_BYTES = 10 * 1024 * 1024;
const MIN_ANALYZING_MS = 1800; // LLM lokal bisa 30-120 detik; tombol tetap 'Menganalisis...'

let mode = "text";
let file = null;
let analyzing = false;

const show = (el, on) => el.classList.toggle("hidden", !on);

function hideResults() {
  show($("done-banner"), false);
  show($("normalized-card"), false);
}

function refreshButton() {
  const ready = mode === "text"
    ? titleInput.value.trim() !== "" && textarea.value.trim() !== ""
    : file !== null;
  startButton.disabled = !ready || analyzing;
}

function setMode(next) {
  mode = next;
  tabs.forEach((tab) => tab.classList.toggle("tab-active", tab.dataset.mode === next));
  show($("panel-text"), next === "text");
  show($("panel-upload"), next === "upload");
  refreshButton();
}

tabs.forEach((tab) => tab.addEventListener("click", () => setMode(tab.dataset.mode)));

textarea.addEventListener("input", () => {
  $("char-count").textContent = textarea.value.length.toLocaleString("id-ID");
  hideResults();
  refreshButton();
});

titleInput.addEventListener("input", () => {
  $("title-count").textContent = titleInput.value.length;
  hideResults();
  refreshButton();
});

$("use-example").addEventListener("click", () => {
  textarea.value = $("use-example").dataset.example;
  textarea.dispatchEvent(new Event("input"));
});

// Unggah dokumen
const zone = $("upload-zone");
const input = $("file-input");

function selectFile(next) {
  if (!next) return;
  const error = $("file-error");
  const dot = next.name.lastIndexOf(".");
  const extension = dot >= 0 ? next.name.slice(dot).toLowerCase() : "";
  let message = "";
  if (!SUPPORTED.includes(extension)) message = "Format belum didukung. Gunakan PDF atau DOCX.";
  else if (next.size > MAX_BYTES) message = "Ukuran dokumen melebihi batas maksimum 10 MB.";

  if (message) {
    file = null;
    error.textContent = message;
    show(error, true);
  } else {
    file = next;
    show(error, false);
    hideResults();
  }
  $("file-name").textContent = file ? file.name : "";
  $("file-size").textContent = file ? (file.size / 1024 / 1024).toFixed(2) : "";
  show($("file-empty"), !file);
  show($("file-chosen"), !!file);
  show($("icon-upload"), !file);
  show($("icon-check"), !!file);
  refreshButton();
}

zone.addEventListener("click", () => input.click());
input.addEventListener("click", (event) => event.stopPropagation());
input.addEventListener("change", () => selectFile(input.files[0]));
zone.addEventListener("dragenter", () => zone.classList.add("upload-zone-active"));
zone.addEventListener("dragleave", () => zone.classList.remove("upload-zone-active"));
zone.addEventListener("dragover", (event) => event.preventDefault());
zone.addEventListener("drop", (event) => {
  event.preventDefault();
  zone.classList.remove("upload-zone-active");
  selectFile(event.dataTransfer.files[0]);
});

// Mulai analisis
function setAnalyzing(on) {
  analyzing = on;
  $("start-label").textContent = on ? "Menganalisis..." : "Mulai analisis";
  $("spark-icon").classList.toggle("animate-spin", on);
  show($("arrow-icon"), !on);
  refreshButton();
}

startButton.addEventListener("click", async () => {
  if (startButton.disabled) return;
  let request_init;
  if (mode === "text") {
    request_init = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "text", title: titleInput.value.trim(), text: textarea.value }),
    };
  } else {
    const form = new FormData();
    form.append("file", file);
    request_init = { method: "POST", body: form };
  }
  hideResults();
  setAnalyzing(true);
  const wait = new Promise((resolve) => setTimeout(resolve, MIN_ANALYZING_MS));
  try {
    const request = fetch("/api/analisis", request_init).then(async (response) => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Analisis gagal.");
      return payload;
    });
    const [payload] = await Promise.all([request, wait]);
    $("result-link").href = payload.result_url;
    if (payload.normalized) {
      $("normalized-text").textContent = payload.normalized.text;
      $("normalized-changes").textContent = payload.normalized.changes;
      show($("normalized-card"), true);
    }
    show($("done-banner"), true);
  } catch (error) {
    alert(error.message);
  } finally {
    setAnalyzing(false);
  }
});

refreshButton();
