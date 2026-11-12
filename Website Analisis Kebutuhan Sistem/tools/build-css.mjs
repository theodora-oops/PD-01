// Membuat static/css/pages/<halaman>.css: satu file CSS biasa per halaman.
// Hanya kelas yang dipakai halaman tersebut (template + JS-nya) yang disertakan.
import { execFileSync } from "node:child_process"
import { mkdirSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const bin = join(root, "node_modules", ".bin", "tailwindcss")
const outDir = join(root, "static", "css", "pages")
mkdirSync(outDir, { recursive: true })

const shared = ["templates/_macros.html", "templates/base.html", "data.py", "analyze.py"]
const appShell = ["templates/app.html", "templates/_card.html"]
const pages = {
  login: [],
  dashboard: appShell,
  workspace: appShell,
  projects: appShell,
  history: appShell,
  help: appShell,
  settings: appShell,
  profile: appShell,
  result: appShell,
}

for (const [page, extra] of Object.entries(pages)) {
  const sources = [...shared, ...extra, `templates/${page}.html`, `static/js/${page}.js`]
  const input = join(root, "tools", `.input-${page}.css`)
  writeFileSync(
    input,
    [
      '@import "tailwindcss" source(none);',
      '@import "./theme.css";',
      ...sources.map((file) => `@source "../${file}";`),
      "",
    ].join("\n"),
  )
  try {
    execFileSync(bin, ["-i", input, "-o", join(outDir, `${page}.css`)], { stdio: "inherit" })
  } finally {
    rmSync(input, { force: true })
  }
}
