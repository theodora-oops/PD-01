"""Normalisasi teks dasar berbasis aturan (huruf, spasi, singkatan/bahasa gaul)."""

import re
import unicodedata

DICTIONARY = {
    "yg": "yang", "dgn": "dengan", "dg": "dengan", "utk": "untuk", "untk": "untuk",
    "krn": "karena", "karna": "karena", "tdk": "tidak", "gak": "tidak", "ga": "tidak",
    "nggak": "tidak", "gk": "tidak", "sy": "saya", "aku": "saya", "gw": "saya",
    "gue": "saya", "sbg": "sebagai", "sbb": "sebab", "dr": "dari", "dlm": "dalam",
    "pd": "pada", "tsb": "tersebut", "jg": "juga", "jga": "juga", "bs": "bisa",
    "blm": "belum", "sdh": "sudah", "udah": "sudah", "udh": "sudah", "bgt": "sangat",
    "banget": "sangat", "aja": "saja", "doang": "saja", "trs": "terus", "tp": "tetapi",
    "tapi": "tetapi", "klo": "jika", "kalo": "jika", "kl": "jika", "hrs": "harus",
    "perlu": "perlu", "dpt": "dapat", "dapet": "dapat", "org": "orang", "spy": "supaya",
    "agar": "agar", "mhs": "mahasiswa", "dsn": "dosen", "prodi": "program studi",
    "sistem": "sistem", "app": "aplikasi", "apk": "aplikasi", "dll": "dan lain-lain",
    "dsb": "dan sebagainya", "dst": "dan seterusnya", "yaitu": "yaitu", "hp": "ponsel",
    "admin": "admin", "login": "login", "unutk": "untuk",
}


def _expand_word(word: str) -> str:
    lower = word.lower()
    replacement = DICTIONARY.get(lower)
    if not replacement or replacement == lower:
        return word
    if word[0].isupper() and len(word) > 1 and word != word.upper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def normalize_text(value: str) -> dict:
    """Mengembalikan {"text": teks_rapi, "changes": jumlah_perubahan}."""
    changes = 0

    def track(before: str, after: str) -> str:
        nonlocal changes
        if before != after:
            changes += 1
        return after

    text = track(value, unicodedata.normalize("NFKC", value))
    text = track(text, re.sub("[\u200b-\u200d\ufeff]", "", text))
    text = track(text, re.sub("[\u201c\u201d]", '"', text))
    text = track(text, re.sub("[\u2018\u2019]", "'", text))
    text = track(text, re.sub(r"\r\n?", "\n", text))
    text = track(text, re.sub(r"[ \t]+", " ", text))
    text = track(text, re.sub(r"\n{3,}", "\n\n", re.sub(r" *\n *", "\n", text)))

    # huruf berulang berlebihan: "bangeeet" -> "banget"
    text = track(text, re.sub(r"([a-zA-Z])\1{2,}", r"\1", text))
    # tanda baca berulang: "!!!" -> "!"
    text = track(
        text,
        re.sub(r"([!?.,;:])\1+", lambda m: "..." if m.group(1) == "." else m.group(1), text),
    )
    text = track(text, re.sub(r" +([,.;:!?])", r"\1", text))
    text = track(text, re.sub(r"([,;:!?])(?=\S)", r"\1 ", text))

    def expand(match: re.Match) -> str:
        nonlocal changes
        word = match.group(0)
        nxt = _expand_word(word)
        if nxt != word:
            changes += 1
        return nxt

    text = re.sub(r"[A-Za-z]+", expand, text)
    text = track(text, re.sub(r"\b(\w+)( \1\b)+", r"\1", text, flags=re.I | re.A))

    lines = []
    for line in text.split("\n"):
        trimmed = line.strip()
        if not trimmed:
            lines.append(trimmed)
            continue
        capitalized = re.sub(
            r"(^|[.!?]\s+)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            trimmed,
        )
        if capitalized != trimmed:
            changes += 1
        lines.append(capitalized)
    text = "\n".join(lines).strip()

    if text and not re.search(r"[.!?]$", text):
        text += "."
        changes += 1

    return {"text": text, "changes": changes}
