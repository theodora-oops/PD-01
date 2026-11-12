// Menjalankan aplikasi Flask: `npm run dev` (atau `npm run setup` untuk memasang Flask).
import { spawnSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const candidates = process.platform === "win32" ? ["py", "python", "python3"] : ["python3", "python"]

function findPython() {
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ["--version"], { stdio: "ignore" })
    if (probe.status === 0) return cmd
  }
  console.error("Python 3 tidak ditemukan. Pasang Python 3.9+ terlebih dahulu.")
  process.exit(1)
}

const python = findPython()
const args = process.argv.includes("--install")
  ? ["-m", "pip", "install", "-r", "requirements.txt"]
  : ["app.py"]
const result = spawnSync(python, args, { cwd: root, stdio: "inherit" })
process.exit(result.status ?? 1)
