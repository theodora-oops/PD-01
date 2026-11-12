// Pengaturan: disimpan ke database lewat /api/pengaturan dan /api/kata-sandi.
function show(el, on) {
  el.classList.toggle("hidden", !on);
  el.classList.toggle("flex", on);
}

document.querySelectorAll(".toggle").forEach((button) => {
  const knob = button.querySelector(".toggle-knob");
  button.addEventListener("click", () => {
    const on = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(on));
    button.classList.toggle("bg-brand", on);
    button.classList.toggle("bg-line", !on);
    knob.classList.toggle("translate-x-5", on);
  });
});

const saved = document.getElementById("settings-saved");
const settingsError = document.getElementById("settings-error");
let savedTimer;
document.getElementById("save-settings").addEventListener("click", async () => {
  settingsError.classList.add("hidden");
  const on = (key) => document.querySelector(`.toggle[data-key="${key}"]`).getAttribute("aria-pressed") === "true";
  try {
    const response = await fetch("/api/pengaturan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        done: on("done"), email: on("email"), tips: on("tips"),
        language: document.getElementById("pref-language").value,
        detail: document.getElementById("pref-detail").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Pengaturan tidak dapat disimpan.");
    show(saved, true);
    clearTimeout(savedTimer);
    savedTimer = setTimeout(() => show(saved, false), 2500);
  } catch (error) {
    settingsError.textContent = error.message;
    settingsError.classList.remove("hidden");
  }
});

const form = document.getElementById("password-form");
const submit = document.getElementById("password-submit");
const ok = document.getElementById("password-ok");
const error = document.getElementById("password-error");
const inputs = {
  current: form.querySelector('[data-field="current"]'),
  next: form.querySelector('[data-field="next"]'),
  confirm: form.querySelector('[data-field="confirm"]'),
};

function syncSubmit() {
  submit.disabled = !inputs.current.value || !inputs.next.value;
}
form.addEventListener("input", syncSubmit);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  show(ok, false);
  error.classList.add("hidden");
  let message = "";
  if (inputs.next.value.length < 8) message = "Kata sandi baru minimal 8 karakter.";
  else if (inputs.next.value !== inputs.confirm.value) message = "Konfirmasi kata sandi tidak cocok.";
  if (!message) {
    try {
      const response = await fetch("/api/kata-sandi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current: inputs.current.value, next: inputs.next.value }),
      });
      const payload = await response.json();
      if (!response.ok) message = payload.error || "Kata sandi tidak dapat diperbarui.";
    } catch (e) {
      message = "Server tidak dapat dihubungi.";
    }
  }
  if (message) {
    error.textContent = message;
    error.classList.remove("hidden");
    return;
  }
  show(ok, true);
  form.reset();
  syncSubmit();
});
