"""Utilitas teks bersama untuk few-shot, validasi, dan evaluasi."""
import re

STOP = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "atau", "serta", "agar",
    "akan", "dapat", "bisa", "ini", "itu", "adalah", "oleh", "sebagai", "juga", "lalu", "kemudian",
    "kalau", "jika", "saat", "setelah", "sebelum", "tiap", "setiap", "secara", "sistem", "saya",
    "ingin", "mau", "bikin", "membuat", "memungkinkan", "para", "nya", "sudah", "belum", "lebih",
}


def _simple(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]


def _crude_stem(word):
    for suf in ("kan", "nya", "lah", "an", "i"):
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            word = word[: -len(suf)]
            break
    for pre in ("meng", "meny", "mem", "men", "me", "peng", "peny", "pem", "pen", "per", "ber", "di", "ter"):
        if word.startswith(pre) and len(word) - len(pre) >= 4:
            return word[len(pre):]
    return word


def tokens(text, stem=True):
    """Token bermakna. Memakai Sastrawi bila terpasang, jika tidak memakai stemming sederhana."""
    if stem:
        try:
            from nlp_utils import preprocess
            return preprocess(text, stem=True)
        except Exception:
            return [_crude_stem(w) for w in _simple(text)]
    return _simple(text)


def dice(a, b):
    a, b = set(a), set(b)
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0
