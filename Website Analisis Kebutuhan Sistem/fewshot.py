"""Memilih contoh analisis dari dataset untuk disuntikkan ke prompt (few-shot)."""
import json
import os
from functools import lru_cache
from pathlib import Path

from textutil import dice, tokens

DEFAULT_PATH = Path(__file__).parent / "dataset" / "sikara_gold.jsonl"

HEADER = ("\nContoh analisis yang benar (hanya sebagai panduan gaya, kedalaman, dan format; "
          "JANGAN menyalin isinya dan jangan menambah fitur yang tidak didukung teks pengguna):")


@lru_cache(maxsize=4)
def load_dataset(path=None):
    path = Path(path or os.environ.get("DATASET_PATH") or DEFAULT_PATH)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def select_examples(text, k=2, pool=None):
    """k contoh paling mirip dengan teks (kemiripan token), hanya dari split 'example'."""
    pool = pool if pool is not None else [c for c in load_dataset() if c.get("split") == "example"]
    pool = [c for c in pool if c.get("summary") and c.get("user_stories")]
    q = tokens(text)
    ranked = sorted(pool, key=lambda c: dice(q, tokens(c["input"])), reverse=True)
    return ranked[:k]


def build_examples_text(text, k=2, pool=None):
    chosen = select_examples(text, k, pool) if k and k > 0 else []
    parts = []
    for i, ex in enumerate(chosen, 1):
        out = {
            "summary": ex["summary"],
            "actors": [{"name": a["name"], "role": a["role"], "description": a.get("description", "")}
                       for a in ex["actors"]],
            "requirements": [{"actor": r["actor"], "description": r["text"], "priority": r["priority"]}
                             for r in ex["requirements"]],
            "user_stories": ex["user_stories"],
            "notes": [],
        }
        parts.append(f"\n[Contoh {i}]\nDeskripsi: {ex['input']}\nJawaban: {json.dumps(out, ensure_ascii=False)}")
    return (HEADER + "".join(parts)) if parts else ""
