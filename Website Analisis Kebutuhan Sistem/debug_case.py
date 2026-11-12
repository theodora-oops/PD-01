"""Periksa SATU kasus uji: kunci jawaban vs keluaran analisis aturan, tanpa memanggil LLM.

Pakai:  python debug_case.py dp-01
Tujuan: memastikan skor rendah berasal dari kemampuan analisis, bukan dari kesalahan pada kunci jawaban
        (nama aktor, sinonim, atau terjemahan).
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import fewshot  # noqa: E402
from analyze import analyze_text  # noqa: E402
from evaluate import actor_drop_set, actor_match, req_tokens  # noqa: E402
from textutil import dice, tokens  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cid = sys.argv[1]
    base = Path(fewshot.DEFAULT_PATH).parent
    cases = fewshot.load_dataset()
    extra = base / "dalpiaz_id.jsonl"
    if extra.exists():
        cases = cases + fewshot.load_dataset(str(extra))
    case = next((c for c in cases if c["id"] == cid), None)
    if not case:
        sys.exit(f"Kasus {cid} tidak ditemukan. Tersedia: {[c['id'] for c in cases if c['split']=='eval']}")
    a = analyze_text(case["input"])

    print(f"=== {cid} ({case['domain']}) ===\nINPUT:\n{case['input']}\n")
    print("AKTOR ACUAN:")
    for g in case["actors"]:
        hit = [p[0] for p in a["actors"] if actor_match(g, p[0])]
        print(f"  - {g['name']}  sinonim={g.get('aliases', [])}  -> cocok dengan: {hit or 'TIDAK ADA'}")
    print("AKTOR HASIL ANALISIS ATURAN:", [p[0] for p in a["actors"]])
    print("\nKEBUTUHAN ACUAN dan padanan terbaik dari analisis aturan (skor Dice, ambang 0.35; nama aktor diabaikan):")
    drop = actor_drop_set(case, a)
    pt = [(r[1], req_tokens(r[1], drop)) for r in a["reqs"]]
    for g in case["requirements"]:
        best = max(((dice(req_tokens(g["text"], drop), t), txt) for txt, t in pt), default=(0.0, "-"))
        print(f"  [{best[0]:.2f}] {g['text']}\n         ~ {best[1][:110]}")
    if case.get("user_stories"):
        print("\nUSER STORY ACUAN:")
        for s in case["user_stories"]:
            print(f"  sebagai {s['actor']}, {s['want']}  (agar {s['benefit'] or '-'})")
    if case.get("source_stories_en"):
        print("\nSTORY ASLI (Inggris) untuk membandingkan terjemahan:")
        for s in case["source_stories_en"]:
            print(f"  As a {s['actor']}, I want {s['want']}" + (f", so that {s['benefit']}" if s["benefit"] else ""))


if __name__ == "__main__":
    main()
