// Akordeon FAQ dan pencarian topik.
const items = document.querySelectorAll(".faq-item");
const empty = document.getElementById("faq-empty");
const search = document.getElementById("faq-search");

items.forEach((item) => {
  const toggle = item.querySelector(".faq-toggle");
  const answer = item.querySelector(".faq-answer");
  const chevron = item.querySelector(".faq-chevron");
  toggle.addEventListener("click", () => {
    const willOpen = answer.classList.contains("hidden");
    items.forEach((other) => {
      other.querySelector(".faq-answer").classList.add("hidden");
      other.querySelector(".faq-chevron").classList.remove("rotate-90");
      other.querySelector(".faq-toggle").setAttribute("aria-expanded", "false");
    });
    if (willOpen) {
      answer.classList.remove("hidden");
      chevron.classList.add("rotate-90");
      toggle.setAttribute("aria-expanded", "true");
    }
  });
});

search.addEventListener("input", () => {
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  items.forEach((item) => {
    const show = item.dataset.text.includes(query);
    item.classList.toggle("hidden", !show);
    if (show) visible += 1;
  });
  empty.classList.toggle("hidden", visible > 0);
});
