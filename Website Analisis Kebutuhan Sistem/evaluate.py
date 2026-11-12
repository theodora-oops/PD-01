"""Evaluasi kualitas analisis terhadap dataset acuan (gold) -- untuk bukti validasi di laporan/skripsi.

Contoh:
    python evaluate.py --modes rule                  # tanpa LLM (offline)
    python evaluate.py --modes rule,zero,few --sleep 8
Hasil: folder evaluasi/ (ringkasan.csv dan detail.md).

Mode:  rule = analisis berbasis aturan lama | zero = LLM tanpa contoh | few = LLM + contoh few-shot.
Hanya kasus split "eval" yang diuji; contoh few-shot hanya diambil dari split "example" (tanpa kebocoran).
"""
import argparse
import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import fewshot  # noqa: E402
import validate  # noqa: E402
from analyze import analyze_text  # noqa: E402
from llm_service import analyze_with_llm  # noqa: E402
from textutil import dice, tokens  # noqa: E402


def _tok_match(a, b):
    """Dua token dianggap sama bila identik atau salah satunya awalan yang lain (admin ~ administrator)."""
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def _names_match(g, p):
    """Semua token dari nama yang lebih pendek harus ada di nama yang lebih panjang."""
    if not g or not p:
        return False
    short, long_ = (g, p) if len(g) <= len(p) else (p, g)
    return all(any(_tok_match(t, u) for u in long_) for t in short)


def actor_match(gold, pred_name):
    p = tokens(pred_name)
    return any(_names_match(tokens(label), p) for label in [gold["name"]] + gold.get("aliases", []))


def actor_drop_set(case, analysis):
    """Token nama aktor (acuan dan prediksi). Dibuang saat mencocokkan kebutuhan, karena aktor sudah dinilai
    terpisah; tanpa ini, 'Pengguna' vs 'Admin' menurunkan skor kebutuhan yang isinya sebenarnya sama."""
    names = [a["name"] for a in case["actors"]] + [p[0] for p in analysis["actors"]]
    return {w for n in names for w in tokens(n)}


def req_tokens(text, drop=frozenset()):
    t = tokens(text)
    return [w for w in t if w not in drop] or t


def match_requirements(gold_reqs, pred_reqs, threshold, drop=frozenset()):
    return match_tokens([req_tokens(r["text"], drop) for r in gold_reqs],
                        [req_tokens(r[1], drop) for r in pred_reqs], threshold)


def match_stories(gold_stories, pred_stories, threshold):
    """User story dicocokkan lewat bagian 'want' (tujuan)."""
    return match_tokens([tokens(s["want"]) for s in gold_stories], [tokens(s[1]) for s in pred_stories], threshold)


def match_tokens(gt, pt, threshold):
    """Pencocokan satu-ke-satu (serakah) berdasar kemiripan token. Mengembalikan daftar (i_gold, j_pred, skor)."""
    pairs = sorted(((dice(gt[i], pt[j]), i, j) for i in range(len(gt)) for j in range(len(pt))), reverse=True)
    used_g, used_p, out = set(), set(), []
    for score, i, j in pairs:
        if score < threshold:
            break
        if i not in used_g and j not in used_p:
            used_g.add(i); used_p.add(j); out.append((i, j, score))
    return out


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def run_mode(mode, case, k, pool):
    if mode == "rule":
        return analyze_text(case["input"]), "rule"
    kk = 0 if mode == "zero" else k
    analysis, engine, _ = analyze_with_llm(case["input"], examples_k=kk, example_pool=pool, validate_output=False)
    return analysis, engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="rule,zero,few")
    ap.add_argument("--k", type=int, default=2, help="jumlah contoh few-shot")
    ap.add_argument("--threshold", type=float, default=0.35, help="ambang kemiripan kebutuhan dianggap cocok")
    ap.add_argument("--sleep", type=float, default=8.0, help="jeda antar panggilan LLM (detik), hindari batas kuota")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah kasus uji (0 = semua)")
    ap.add_argument("--no-cache", action="store_true", help="abaikan hasil LLM yang tersimpan (panggil ulang)")
    ap.add_argument("--skip", default="", help="id kasus yang dikecualikan, pisahkan koma, mis. 'dp-02,dp-05'")
    ap.add_argument("--only", default="", help="hanya kasus dengan awalan id ini, mis. 'ev-' (buatan sendiri) atau 'dp-' (hasil impor Dalpiaz)")
    args = ap.parse_args()

    data = fewshot.load_dataset()
    pool = [c for c in data if c["split"] == "example"]  # contoh few-shot: hanya dari dataset utama
    imported = Path(fewshot.DEFAULT_PATH).parent / "dalpiaz_id.jsonl"
    extra = fewshot.load_dataset(str(imported)) if imported.exists() else []
    skip = {x.strip() for x in args.skip.split(",") if x.strip()}
    cases = [c for c in data + extra if c["split"] == "eval" and c["id"].startswith(args.only) and c["id"] not in skip]
    print(f"{len(cases)} kasus uji ({sum(1 for c in cases if c['id'].startswith('dp-'))} dari impor Dalpiaz)")
    if args.limit:
        cases = cases[: args.limit]
    out_dir = Path("evaluasi"); out_dir.mkdir(exist_ok=True)

    cache_path = out_dir / "cache.json"
    cache = {} if args.no_cache or not cache_path.exists() else json.loads(cache_path.read_text(encoding="utf-8"))
    provider = os.environ.get("LLM_PROVIDER", "none").lower()
    model_tag = f"{provider}:{os.environ.get(provider.upper() + '_MODEL', '')}"
    fails, stop = 0, False

    rows, detail = [], ["# Detail evaluasi\n", f"Ambang kemiripan: {args.threshold}. Periksa manual kecocokan yang meragukan.\n"]
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        if stop:
            break
        for case in cases:
            key = f"{mode}|{case['id']}|{model_tag}|k{args.k}"
            cached = mode != "rule" and key in cache
            if cached:
                analysis, engine = cache[key], "llm"
            else:
                analysis, engine = run_mode(mode, case, args.k, pool)
            if mode != "rule" and engine != "llm":
                print(f"[{mode}] {case['id']}: LLM gagal, dilewati")
                rows.append([mode, case["id"], "GAGAL"] + [""] * 13)
                fails += 1
                if fails >= 2:
                    print("\nDua kegagalan LLM berturut-turut: kuota kemungkinan habis. Hasil yang sudah selesai tersimpan "
                          "di evaluasi\\cache.json. Jalankan perintah yang sama lagi nanti; bagian yang sudah selesai "
                          "tidak memanggil LLM lagi.")
                    stop = True
                    break
                continue
            fails = 0
            if mode != "rule" and not cached:
                cache[key] = analysis
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            # aktor
            g_act, p_act = case["actors"], [a[0] for a in analysis["actors"]]
            tp_a = sum(1 for g in g_act if any(actor_match(g, p) for p in p_act))          # acuan yang ditemukan
            tp_a_pred = sum(1 for p in p_act if any(actor_match(g, p) for g in g_act))      # prediksi yang benar
            ap_ = tp_a_pred / len(p_act) if p_act else 0.0
            ar_ = tp_a / len(g_act)
            af_ = 2 * ap_ * ar_ / (ap_ + ar_) if ap_ + ar_ else 0.0
            # kebutuhan
            matches = match_requirements(case["requirements"], analysis["reqs"], args.threshold,
                                         actor_drop_set(case, analysis))
            rp, rr, rf = prf(len(matches), len(analysis["reqs"]), len(case["requirements"]))
            g_st = case.get("user_stories") or []
            if g_st:
                p_st = analysis["stories"]
                sm = match_stories(g_st, p_st, args.threshold)
                sp, sr, sf = prf(len(sm), len(p_st), len(g_st))
                complete = (sum(1 for x in p_st if len(x) >= 3 and all(str(y).strip() for y in x[:3])) / len(p_st)) if p_st else 0.0
                sp, sr, sf, complete = round(sp, 2), round(sr, 2), round(sf, 2), round(complete, 2)
            else:
                sm, sp, sr, sf, complete = [], "", "", "", ""
            v = validate.check(analysis)
            vrate = v["passed"] / v["checked"] if v["checked"] else 0.0
            rows.append([mode, case["id"], "ok", round(ap_, 2), round(ar_, 2), round(af_, 2),
                         round(rp, 2), round(rr, 2), round(rf, 2), round(vrate, 2),
                         len(analysis["reqs"]), len(case["requirements"]), sp, sr, sf, complete])
            gi = {i for i, _, _ in matches}; pj = {j for _, j, _ in matches}
            detail.append(f"\n## [{mode}] {case['id']} - {case['domain']}\n")
            detail.append(f"- Recall kebutuhan {rr:.2f}, precision {rp:.2f}\n")
            for i, g in enumerate(case["requirements"]):
                if i not in gi:
                    detail.append(f"- TIDAK DITEMUKAN (acuan): {g['text']}\n")
            for j, p in enumerate(analysis["reqs"]):
                if j not in pj:
                    detail.append(f"- EKSTRA (tidak ada di acuan, periksa apakah valid): {p[1]}\n")
            if g_st:
                sgi = {i for i, _, _ in sm}; spj = {j for _, j, _ in sm}
                for i, g in enumerate(g_st):
                    if i not in sgi:
                        detail.append(f"- USER STORY TIDAK DITEMUKAN (acuan): sebagai {g['actor']}, {g['want']}\n")
                for j, p in enumerate(analysis["stories"]):
                    if j not in spj:
                        detail.append(f"- USER STORY EKSTRA: sebagai {p[0]}, {p[1]}\n")
            extra = f" storyF1={sf}" if g_st else ""
            print(f"[{mode}] {case['id']}: R={rr:.2f} P={rp:.2f} aktorF1={af_:.2f} lolos-cek={vrate:.2f}{extra}")
            if mode != "rule" and not cached:
                time.sleep(args.sleep)

    header = ["mode", "kasus", "status", "aktor_P", "aktor_R", "aktor_F1", "req_P", "req_R", "req_F1",
              "lolos_cek", "n_prediksi", "n_acuan", "story_P", "story_R", "story_F1", "story_lengkap"]
    with open(out_dir / "ringkasan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    (out_dir / "detail.md").write_text("".join(detail), encoding="utf-8")

    print("\n=== RATA-RATA per mode ===")
    for mode in dict.fromkeys(r[0] for r in rows):
        ok = [r for r in rows if r[0] == mode and r[2] == "ok"]
        if ok:
            avg = lambda i: sum(r[i] for r in ok) / len(ok)
            line = f"{mode:5} n={len(ok)}  aktorF1={avg(5):.2f}  req P={avg(6):.2f} R={avg(7):.2f} F1={avg(8):.2f}  lolos-cek={avg(9):.2f}"
            st = [r for r in ok if r[14] != ""]
            if st:
                line += f"  | story n={len(st)} P={sum(r[12] for r in st)/len(st):.2f} R={sum(r[13] for r in st)/len(st):.2f} F1={sum(r[14] for r in st)/len(st):.2f} lengkap={sum(r[15] for r in st)/len(st):.2f}"
            print(line)
    print(f"\nTersimpan di {out_dir}/ringkasan.csv dan {out_dir}/detail.md")


if __name__ == "__main__":
    main()
