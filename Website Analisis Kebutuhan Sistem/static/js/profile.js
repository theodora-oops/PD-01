// Mode ubah profil: perubahan disimpan ke database lewat /api/profil.
const editable = ["name", "role", "unit", "email"];
const inputs = Object.fromEntries(
  editable.map((key) => [key, document.querySelector(`[data-field="${key}"]`)]),
);
const edit = document.getElementById("edit-profile");
const save = document.getElementById("save-profile");
const cancel = document.getElementById("cancel-profile");
const saved = document.getElementById("profile-saved");
let committed = Object.fromEntries(editable.map((key) => [key, inputs[key].value]));
let savedTimer;

// Tombol bergaya kustom memakai atribut hidden agar benar-benar tersembunyi.
function toggle(el, on, display) {
  if (display === "flex") {
    el.classList.toggle("hidden", !on);
    el.classList.toggle("flex", on);
  } else {
    el.hidden = !on;
  }
}

function setEditing(on) {
  editable.forEach((key) => {
    inputs[key].disabled = !on;
    inputs[key].closest(".input-shell").classList.toggle("opacity-70", !on);
  });
  toggle(edit, !on, "button");
  toggle(save, on, "button");
  toggle(cancel, on, "button");
}

function initials(name) {
  return name.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase();
}

edit.addEventListener("click", () => {
  toggle(saved, false, "flex");
  setEditing(true);
});

inputs.name.addEventListener("input", () => {
  save.disabled = !inputs.name.value.trim();
});

cancel.addEventListener("click", () => {
  editable.forEach((key) => (inputs[key].value = committed[key]));
  save.disabled = false;
  setEditing(false);
});

const errorBox = document.getElementById("profile-error");

save.addEventListener("click", async () => {
  errorBox.classList.add("hidden");
  const body = Object.fromEntries(editable.map((key) => [key, inputs[key].value]));
  save.disabled = true;
  try {
    const response = await fetch("/api/profil", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Profil tidak dapat disimpan.");
    committed = body;
    document.getElementById("profile-name").textContent = committed.name;
    document.getElementById("profile-role").textContent = committed.role;
    document.getElementById("profile-initials").textContent = payload.initials || initials(committed.name);
    setEditing(false);
    toggle(saved, true, "flex");
    clearTimeout(savedTimer);
    savedTimer = setTimeout(() => toggle(saved, false, "flex"), 2500);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    save.disabled = !inputs.name.value.trim();
  }
});
