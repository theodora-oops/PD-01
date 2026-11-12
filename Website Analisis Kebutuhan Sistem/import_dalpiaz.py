"""Ubah dataset user stories Dalpiaz (Inggris) menjadi kasus uji SIKARA berbahasa Indonesia, memakai LLM.

Persiapan:
  1. Unduh "Download All" dari https://data.mendeley.com/datasets/7zbk8zsd8y/2 lalu ekstrak
     (isinya sekitar 22 berkas .txt, satu user story per baris) ke satu folder, misalnya dalpiaz_raw\
  2. Pastikan .env berisi LLM_PROVIDER=gemini dan GEMINI_API_KEY.
Jalankan:
  python import_dalpiaz.py --src dalpiaz_raw --limit 3        (coba dulu 3 produk)
  python import_dalpiaz.py --src dalpiaz_raw                   (semua)
Hasil: dataset/dalpiaz_id.jsonl (ikut dibaca otomatis oleh evaluate.py).

Cara kerja per produk (1 panggilan LLM):
  - Parsing user story dilakukan dengan aturan (bukan LLM), sehingga isi aslinya tetap terlacak.
  - LLM menerjemahkan peran/tujuan/manfaat ke Bahasa Indonesia dan menulis deskripsi awam sebagai INPUT.
  - Kebutuhan acuan dibentuk deterministik: "Sistem memungkinkan <peran> <tujuan>."
Lisensi data asal: CC BY 4.0 (Dalpiaz). Lihat dataset/ATTRIBUTION.md.
"""
import argparse
import json
import random
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import llm_service as L  # noqa: E402

STORY_RE = re.compile(
    r"^\s*as\s+(?:an?|the)\s+(?P<actor>.+?)\s*,?\s+i\s+(?:want|need|would\s+like|wish|am\s+able|can)\s*(?:to\s+)?"
    r"(?P<want>.+?)(?:\s*,?\s*(?:so\s+that|so|in\s+order\s+to)\s+(?P<benefit>.+?))?\s*[.!]?\s*$",
    re.I)
PREFIX_RE = re.compile(r"^\s*(?:\d+[\.\):]|[A-Za-z]{1,6}-?\d+[:\.\)])\s*")

SYSTEM = """Kamu membantu menyusun dataset uji untuk sistem analisis kebutuhan berbahasa Indonesia.
Input: JSON berisi daftar user story berbahasa Inggris dari satu aplikasi (n, actor, want, benefit).
Tugas:
1. Terjemahkan setiap peran (actor) ke Bahasa Indonesia yang lazim (mis. Customer -> Pelanggan). Peran yang sama HARUS
   memakai nama yang sama. Beri "role_type" (Pengguna | Pengelola | Pemantau) dan 2-3 "aliases" (sinonim Indonesia).
2. Terjemahkan "want" menjadi frasa kata kerja bahasa Indonesia TANPA subjek dan TANPA kata "ingin" (mis. "melihat daftar
   produk"). Terjemahkan "benefit" menjadi frasa tanpa kata "agar" (string kosong bila tidak ada).
3. Tulis "description": 2-4 kalimat bahasa Indonesia santai, seperti orang awam menjelaskan ide sistemnya. Sebutkan SEMUA
   kebutuhan dari semua story secara garis besar, jangan menyalin kalimat story, jangan menambah fitur lain.
Jawab HANYA satu objek JSON valid:
{"description": "...", "actors": [{"en": "...", "name": "...", "role_type": "...", "aliases": ["..."]}],
 "stories": [{"n": 1, "actor_en": "...", "want": "...", "benefit": "..."}]}"""


def parse_file(path):
    stories, skipped = [], 0
    for line in Path(path).read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = PREFIX_RE.sub("", line.strip())
        if not line:
            continue
        m = STORY_RE.match(line)
        if m and len(m.group("want").split()) >= 2:
            stories.append({"actor": m.group("actor").strip(), "want": m.group("want").strip(),
                            "benefit": (m.group("benefit") or "").strip()})
        else:
            skipped += 1
    return stories, skipped


class QuotaExceeded(Exception):
    pass


def call_llm(payload, attempts=3):
    provider = L.os.environ.get("LLM_PROVIDER", "gemini").lower()
    caller = {"gemini": L._call_gemini, "ollama": L._call_ollama, "anthropic": L._call_anthropic}[provider]
    for i in range(1, attempts + 1):
        try:
            raw, model = caller(json.dumps(payload, ensure_ascii=False), SYSTEM)
            return L._parse_json(raw), model
        except Exception as exc:
            msg = str(exc)
            print(f"   percobaan {i} gagal: {type(exc).__name__}: {msg[:120]}")
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                raise QuotaExceeded(msg)
            time.sleep(8 * i)
    return None, None


def build_case(idx, name, picked, data, model):
    amap = {a["en"].strip().lower(): a for a in data["actors"]}
    actors, seen = [], set()
    for a in data["actors"]:
        if a["name"] not in seen:
            seen.add(a["name"])
            actors.append({"name": a["name"], "role": a.get("role_type", "Pengguna"), "description": "",
                           "aliases": a.get("aliases", [])})
    by_n = {s["n"]: s for s in data["stories"]}
    reqs, stories, texts = [], [], set()
    for n, src in enumerate(picked, 1):
        s = by_n.get(n)
        actor = amap.get((s or {}).get("actor_en", src["actor"]).strip().lower())
        if not s or not actor or not s.get("want", "").strip():
            return None, f"story {n} tidak lengkap/tidak terpetakan"
        want = s["want"].strip().rstrip(".")
        text = f"Sistem memungkinkan {actor['name']} {want}."
        if text not in texts:
            texts.add(text)
            reqs.append({"actor": actor["name"], "text": text, "priority": None})
        stories.append({"actor": actor["name"], "want": want, "benefit": s.get("benefit", "").strip()})
    desc = data.get("description", "").strip()
    if not (120 <= len(desc) <= 900):
        return None, f"panjang deskripsi tidak wajar ({len(desc)} karakter)"
    return {"id": f"dp-{idx:02d}", "split": "eval", "domain": name, "status": "translated_ai",
            "source": "Dalpiaz (2018), Mendeley Data, CC BY 4.0; diterjemahkan dan disusun ulang oleh AI",
            "model": model, "input": desc, "actors": actors, "requirements": reqs,
            "user_stories": stories, "source_stories_en": picked}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="folder berisi berkas .txt user stories")
    ap.add_argument("--out", default="dataset/dalpiaz_id.jsonl")
    ap.add_argument("--per-product", type=int, default=8, help="jumlah story per produk yang dipakai")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah produk (0 = semua)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sleep", type=float, default=8.0)
    ap.add_argument("--fresh", action="store_true", help="mulai dari nol (hapus hasil impor sebelumnya)")
    args = ap.parse_args()

    files = sorted(Path(args.src).rglob("*.txt"))
    if args.limit:
        files = files[: args.limit]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.fresh and out.exists():
        out.unlink()
    cases = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()] if out.exists() else []
    done = {c["domain"] for c in cases}
    if cases:
        print(f"Melanjutkan: {len(cases)} kasus sudah ada di {out} (produk yang sama dilewati).")
    for f in files:
        if f.stem in done:
            print(f"{f.name}: sudah ada, dilewati"); continue
        stories, skipped = parse_file(f)
        print(f"{f.name}: {len(stories)} story terbaca, {skipped} baris dilewati")
        if len(stories) < max(5, args.per_product):
            print("   dilewati: story terlalu sedikit"); continue
        picked = random.Random(f"{args.seed}-{f.name}").sample(stories, args.per_product)  # sama setiap dijalankan
        payload = {"stories": [{"n": i, **s} for i, s in enumerate(picked, 1)]}
        try:
            data, model = call_llm(payload)
        except QuotaExceeded:
            print("\nKuota LLM kemungkinan habis. Hasil yang sudah jadi tersimpan; jalankan perintah yang sama "
                  "lagi nanti (produk yang sudah selesai tidak diproses ulang).")
            break
        if not data:
            print("   dilewati: LLM gagal"); continue
        case, err = build_case(len(cases) + 1, f.stem, picked, data, model)
        if err:
            print(f"   dilewati: {err}"); continue
        cases.append(case)
        with open(out, "a", encoding="utf-8") as fh:  # simpan langsung, aman bila terhenti di tengah jalan
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")
        print(f"   OK -> {case['id']} ({len(case['requirements'])} kebutuhan, {len(case['actors'])} aktor)")
        time.sleep(args.sleep)

    print(f"\nTotal {len(cases)} kasus di {out}. WAJIB diperiksa manual sebelum dipakai di laporan.")


if __name__ == "__main__":
    main()
