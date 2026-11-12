"""Pemeriksaan kualitas otomatis untuk kebutuhan hasil analisis (heuristik).

Merujuk pada karakteristik kebutuhan yang baik (ISO/IEC/IEEE 29148): jelas (tidak ambigu),
atomik (satu kebutuhan satu kalimat), konsisten, dan tidak duplikat. Ini pemeriksaan
BANTUAN, bukan pengganti penilaian pakar.
"""
import re

from textutil import dice, tokens

VAGUE = ["cepat", "mudah", "sederhana", "user friendly", "user-friendly", "ramah pengguna", "fleksibel",
         "optimal", "memadai", "secepat mungkin", "sebaik mungkin", "dll", "dsb", "dan lain-lain",
         "dan sebagainya", "canggih", "modern", "handal", "andal", "lancar", "efisien", "efektif",
         "bagus", "beberapa", "banyak"]
_VAGUE_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(v) for v in VAGUE) + r")(?![a-z])", re.I)
_CONJ_RE = re.compile(r"\b(dan|serta|atau)\b", re.I)


def check(analysis):
    reqs = analysis.get("reqs", [])
    actors = {a[0].strip().lower() for a in analysis.get("actors", [])}
    issues, bad = [], set()

    def flag(code, msg):
        issues.append((code, msg)); bad.add(code)

    toks = {}
    for code, text, actor, _prio in reqs:
        words = text.split()
        toks[code] = tokens(text)
        if len(words) < 4:
            flag(code, "terlalu singkat untuk dipahami sebagai kebutuhan")
        elif len(words) > 40:
            flag(code, "terlalu panjang; pertimbangkan dipecah menjadi beberapa kebutuhan")
        m = _VAGUE_RE.search(text)
        if m:
            flag(code, f"mengandung kata yang tidak terukur: \"{m.group(1)}\" (beri ukuran yang jelas)")
        n_conj = len(_CONJ_RE.findall(text))
        if n_conj >= 3 or (n_conj >= 2 and len(words) > 18):
            flag(code, "mungkin memuat lebih dari satu kebutuhan (banyak kata penghubung)")
        if actor and actor.strip().lower() not in actors and actor.strip().lower() != "sistem":
            flag(code, f"aktor \"{actor}\" tidak ada di daftar aktor")
    codes = list(toks)
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            if dice(toks[codes[i]], toks[codes[j]]) >= 0.8:
                flag(codes[j], f"mirip dengan {codes[i]} (kemungkinan duplikat)")
    return {"checked": len(reqs), "passed": len(reqs) - len(bad), "issues": issues}


def annotate(analysis, max_notes=5):
    """Tambahkan hasil pemeriksaan ke catatan analisis (ikut tersimpan di database)."""
    try:
        res = check(analysis)
    except Exception:  # pemeriksaan tidak boleh menggagalkan analisis
        return analysis
    analysis["validation"] = res
    if res["checked"]:
        analysis["notes"].append(
            f"Pemeriksaan otomatis (kata tidak terukur, panjang, duplikasi, konsistensi aktor): "
            f"{res['passed']} dari {res['checked']} kebutuhan lolos.")
        for code, msg in res["issues"][:max_notes]:
            analysis["notes"].append(f"{code}: {msg}.")
    return analysis
