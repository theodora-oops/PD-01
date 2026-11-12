// Pencarian dan filter status pada daftar proyek.
const search = document.getElementById("project-search");
const chips = document.querySelectorAll(".filter-chip");
const cards = document.querySelectorAll(".project-card");
const empty = document.getElementById("project-empty");
const grid = document.getElementById("project-grid");
const ACTIVE = ["border-brand", "bg-brand", "text-white"];
const IDLE = ["border-line", "bg-white", "text-muted", "hover:text-ink"];
let filter = "Semua";

function render() {
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach((card) => {
    const show =
      (filter === "Semua" || card.dataset.status === filter) &&
      card.dataset.title.includes(query);
    card.classList.toggle("hidden", !show);
    card.classList.toggle("flex", show);
    if (show) visible += 1;
  });
  empty.classList.toggle("hidden", visible > 0);
  grid.classList.toggle("hidden", visible === 0);
  grid.classList.toggle("grid", visible > 0);
  chips.forEach((chip) => {
    const on = chip.dataset.filter === filter;
    chip.classList.remove(...ACTIVE, ...IDLE);
    chip.classList.add(...(on ? ACTIVE : IDLE));
  });
}

search.addEventListener("input", render);
chips.forEach((chip) =>
  chip.addEventListener("click", () => {
    filter = chip.dataset.filter;
    render();
  }),
);
