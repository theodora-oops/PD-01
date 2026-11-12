// Menu geser untuk layar < 1024px (tablet dan ponsel).
// Markup ada di templates/app.html; gaya di static/css/responsive.css.
(function () {
  const body = document.body;
  const toggle = document.getElementById("nav-toggle");
  const closeButton = document.getElementById("nav-close");
  const overlay = document.getElementById("nav-overlay");
  const drawer = document.getElementById("mobile-nav");
  if (!toggle || !drawer) return;

  const desktop = window.matchMedia("(min-width: 1024px)");

  function isOpen() {
    return body.classList.contains("mnav-open");
  }

  function setOpen(open) {
    body.classList.toggle("mnav-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    drawer.setAttribute("aria-hidden", String(!open));
    if (open) {
      // Elemen di dalam menu baru bisa menerima fokus beberapa milidetik setelah kelas dipasang
      // (selama transisi visibility berjalan), jadi fokus dipindah sedikit tertunda.
      setTimeout(() => {
        if (isOpen()) (closeButton || drawer).focus();
      }, 80);
    } else {
      toggle.focus();
    }
  }

  toggle.addEventListener("click", () => setOpen(!isOpen()));
  if (closeButton) closeButton.addEventListener("click", () => setOpen(false));
  if (overlay) overlay.addEventListener("click", () => setOpen(false));

  document.addEventListener("keydown", (event) => {
    if (!isOpen()) return;
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    // Fokus papan ketik tetap berada di dalam menu selama menu terbuka.
    if (event.key === "Tab") {
      const items = drawer.querySelectorAll("a[href], button:not([disabled])");
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  // Jika layar diputar/diperlebar sampai >= 1024px, sidebar biasa yang dipakai: tutup menu geser.
  desktop.addEventListener("change", (event) => {
    if (event.matches && isOpen()) {
      body.classList.remove("mnav-open");
      toggle.setAttribute("aria-expanded", "false");
      drawer.setAttribute("aria-hidden", "true");
    }
  });
})();
