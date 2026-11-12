"""Utilitas NLP Bahasa Indonesia + ekstraksi teks dokumen (PDF/DOCX).

Semua library dimuat saat dibutuhkan supaya aplikasi tetap jalan
walaupun sebagian paket belum terpasang.
"""
import re
from functools import lru_cache
from pathlib import Path


# ---------- Ekstraksi teks dokumen ----------
def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages).strip()
    if ext == ".docx":
        import docx  # paket: python-docx
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts).strip()
    raise ValueError(f"Format {ext} belum didukung (gunakan PDF atau DOCX).")


# ---------- Praproses teks Indonesia ----------
@lru_cache(maxsize=1)
def _stemmer():
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
    return StemmerFactory().create_stemmer()


@lru_cache(maxsize=1)
def _stopwords():
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    return set(StopWordRemoverFactory().get_stop_words())


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+(?:-[a-zA-Z]+)*", text.lower())


def preprocess(text: str, stem: bool = True) -> list[str]:
    """Tokenisasi -> buang stopword -> (opsional) stemming Sastrawi."""
    stop = _stopwords()
    tokens = [t for t in tokenize(text) if t not in stop and len(t) > 2]
    if stem:
        s = _stemmer()
        tokens = [s.stem(t) for t in tokens]
    return tokens


def top_keywords(text: str, n: int = 10) -> list[tuple[str, int]]:
    from collections import Counter
    return Counter(preprocess(text)).most_common(n)


# ---------- Embedding / kemiripan semantik (opsional) ----------
@lru_cache(maxsize=1)
def _embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def similarity(a: str, b: str) -> float:
    from sentence_transformers import util
    m = _embedder()
    return float(util.cos_sim(m.encode(a), m.encode(b)))
