// Halaman hasil: pindah tab, filter prioritas, dan cetak laporan.
const tabs = document.querySelectorAll("[data-tab]");
const panels = document.querySelectorAll(".tab-panel");
// Panel yang tampil sebagai grid memakai kelas ini saat aktif.
const GRID_CLASS = { Aktor: "grid", Prioritas: "grid" };

function showTab(name) {
  tabs.forEach((tab) => tab.classList.toggle("tab-active", tab.dataset.tab === name));
  panels.forEach((panel) => {
    const on = panel.dataset.panel === name;
    panel.classList.toggle("hidden", !on);
    const grid = GRID_CLASS[panel.dataset.panel];
    if (grid) panel.classList.toggle(grid, on);
  });
}
tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
showTab("Ringkasan");

const ACTIVE = ["border-brand", "bg-brand", "text-white"];
const IDLE = ["border-line", "bg-white", "text-muted", "hover:text-ink"];
const chips = document.querySelectorAll(".req-chip");
const items = document.querySelectorAll(".req-item");

function filterRequirements(filter) {
  let visible = 0;
  items.forEach((item) => {
    const show = filter === "Semua" || item.dataset.priority === filter;
    item.classList.toggle("hidden", !show);
    item.classList.toggle("flex", show);
    if (show) visible += 1;
  });
  document.getElementById("req-empty").classList.toggle("hidden", visible > 0);
  chips.forEach((chip) => {
    chip.classList.remove(...ACTIVE, ...IDLE);
    chip.classList.add(...(chip.dataset.filter === filter ? ACTIVE : IDLE));
  });
}
chips.forEach((chip) => chip.addEventListener("click", () => filterRequirements(chip.dataset.filter)));

document.getElementById("print-report").addEventListener("click", () => window.print());
