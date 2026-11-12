# SIKARA

Flask + Jinja2 (Python) app. Plain HTML templates, plain CSS, and small vanilla JS files; no React/Vite.

## Run

- `npm run setup` installs Flask (`pip install -r requirements.txt`); `npm run dev` runs `python app.py` (port `$PORT`, default 5000).
- Login username: `nabila_stafpm` (no sign-up).

## Structure

- `app.py` - routes, session login, `/api/analisis` (JSON)
- `normalize.py` - rule-based text normalization (no LLM)
- `analyze.py` - rule-based analyzer: actors, functional requirements, user stories, priorities (no LLM)
- `data.py` - static sample data (projects, history, FAQ, sample result)
- `templates/` - `base.html`, `app.html` (sidebar/topbar shell), `_macros.html` (icons, brand), `_card.html`, one template per page
- `static/js/<page>.js` - page interactions; `static/css/base.css` - shared component styles
- `static/css/pages/<page>.css` - GENERATED per-page CSS. After changing classes in templates, JS, `data.py` or `analyze.py`, run `npm run build:css` (config in `tools/theme.css`, `tools/build-css.mjs`).

## Notes

- Custom classes in `base.css` are unlayered, so they beat Tailwind utilities. Hide `.primary-button`/`.secondary-button` with the `hidden` attribute, not the `hidden` class.
- Document (PDF/DOCX) upload does not read file contents yet; it returns the sample result. LLM integration is not done.
