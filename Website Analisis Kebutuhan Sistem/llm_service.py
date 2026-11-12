"""Analisis kebutuhan sistem dengan LLM (Gemini, Ollama lokal, atau Anthropic API).

Hasilnya dibuat IDENTIK dengan format analyze_text() di analyze.py, sehingga
template result.html tidak perlu diubah. Bila LLM gagal / belum aktif,
otomatis jatuh ke analisis berbasis aturan.

.env:
    LLM_PROVIDER=gemini            # gemini | ollama | anthropic | none
    GEMINI_API_KEY=...             # dari https://aistudio.google.com/apikey
    GEMINI_MODEL=gemini-flash-latest
    OLLAMA_MODEL=qwen2.5:7b
    OLLAMA_HOST=http://localhost:11434
    ANTHROPIC_API_KEY=sk-ant-...
    ANTHROPIC_MODEL=claude-sonnet-5-5
"""
import json
import os
import re

from dotenv import load_dotenv

from analyze import analyze_text  # fallback berbasis aturan
import fewshot
import validate

load_dotenv()

BASE_PROMPT = """Kamu adalah analis kebutuhan sistem (requirements engineer) untuk
Unit Penjaminan Mutu perguruan tinggi. Dari deskripsi yang diberikan, hasilkan analisis
dalam Bahasa Indonesia. Jawab HANYA dengan satu objek JSON valid tanpa teks lain,
dengan bentuk persis:
{
%(norm_field)s "summary": "ringkasan 1-3 kalimat",
 "actors": [{"name": "...", "role": "Pengelola|Pengguna|Pemantau", "description": "..."}],
 "requirements": [{"actor": "nama aktor", "description": "Sistem memungkinkan ... ", "priority": "Tinggi|Sedang|Rendah"}],
 "user_stories": [{"actor": "...", "want": "...", "benefit": "..."}],
 "notes": ["catatan kekurangan deskripsi, misal platform/non-fungsional belum disebut"]
}
Aturan: jangan mengarang fitur yang tidak didukung teks; tandai saran tambahan Anda
dengan "(saran sistem)"; prioritas Tinggi hanya untuk fungsi inti/keamanan/transaksi.%(norm_rule)s"""

NORM_FIELD = ' "normalized_text": "teks asli yang sudah dinormalkan",\n'
NORM_RULE = """
Aturan normalized_text: perbaiki salah ketik, ejaan baku (PUEBI), huruf kapital, tanda baca,
singkatan dan bahasa gaul menjadi baku. JANGAN menambah, menghapus, atau mengubah makna/isi.
Pertahankan istilah teknis asing yang lazim (misal: driver, monitoring, login, dashboard).
Pertahankan struktur kalimat dan urutan aslinya. Analisis di bawahnya dibuat dari teks yang sudah dinormalkan."""


DETAIL_RULES = {
    "Ringkas": "Tingkat detail RINGKAS: 3-5 kebutuhan paling penting, 2-3 user story, kalimat singkat.",
    "Standar": "Tingkat detail STANDAR: 5-10 kebutuhan, 3-6 user story.",
    "Rinci": "Tingkat detail RINCI: 10-20 kebutuhan termasuk non-fungsional (keamanan, kinerja, "
             "ketersediaan), 6-10 user story, setiap kebutuhan spesifik dan dapat diuji.",
}


def build_prompt(normalize: bool, language: str = "Bahasa Indonesia", detail: str = "Standar",
                 examples: str = "") -> str:
    prompt = BASE_PROMPT % {"norm_field": NORM_FIELD if normalize else "",
                            "norm_rule": NORM_RULE if normalize else ""}
    prompt += "\n" + DETAIL_RULES.get(detail, DETAIL_RULES["Standar"])
    if language == "English":
        prompt += ("\nTulis summary, actors, requirements, user_stories, dan notes dalam BAHASA INGGRIS. "
                   "Nilai 'role' dan 'priority' tetap persis seperti pilihan yang diberikan. "
                   "normalized_text (jika diminta) tetap dalam bahasa teks asli.")
    if examples:
        prompt += "\n" + examples + "\nContoh di atas hanya menampilkan sebagian field; tetap isi semua field sesuai format JSON di awal."
    return prompt


PRIORITIES = {"Tinggi", "Sedang", "Rendah"}
GROUPS = [("Tinggi", "Harus ada", "bg-brand"),
          ("Sedang", "Sebaiknya ada", "bg-brand-soft"),
          ("Rendah", "Opsional", "bg-line")]


def _call_gemini(text: str, system: str) -> tuple[str, str]:
    from google import genai
    from google.genai import types
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return r.text, model


def _call_ollama(text: str, system: str) -> tuple[str, str]:
    import ollama
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    r = client.chat(model=model, format="json", options={"temperature": 0.2},
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": text}])
    return r["message"]["content"], model


def _call_anthropic(text: str, system: str) -> tuple[str, str]:
    import anthropic
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    client = anthropic.Anthropic()  # membaca ANTHROPIC_API_KEY dari environment
    r = client.messages.create(model=model, max_tokens=4000, temperature=0.2,
                               system=system,
                               messages=[{"role": "user", "content": text}])
    return "".join(b.text for b in r.content if b.type == "text"), model


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def to_app_format(d: dict) -> dict:
    """Ubah JSON LLM -> format dict yang dipakai result.html."""
    actors = [[a["name"], a.get("role", "Pengguna"), a.get("description", "")]
              for a in d.get("actors", [])]
    reqs, groups = [], {p: [] for p in PRIORITIES}
    for i, r in enumerate(d.get("requirements", []), 1):
        prio = r.get("priority") if r.get("priority") in PRIORITIES else "Sedang"
        reqs.append([f"FR-{i:02d}", r["description"], r.get("actor", "Pengguna"), prio])
        groups[prio].append(r["description"][:120])
    stories = [[s["actor"], s["want"], s["benefit"]] for s in d.get("user_stories", [])]
    features = [[label, css, groups[p]] for p, label, css in GROUPS if groups[p]]
    high = len(groups["Tinggi"])
    score = min(95, 40 + min(35, len(reqs) * 4) + min(10, len(actors) * 3)
                + (5 if not d.get("notes") else 0))
    return {"normalized_text": d.get("normalized_text"),
            "summary": d.get("summary", ""), "actors": actors, "reqs": reqs,
            "stories": stories, "features": features,
            "notes": list(d.get("notes", [])) + ["Hasil dibuat oleh LLM. Tinjau kembali sebelum digunakan."],
            "score": score}


def count_changes(before: str, after: str) -> int:
    """Jumlah bagian kata yang berubah antara teks asli dan hasil normalisasi."""
    import difflib
    x, y = before.split(), after.split()
    ops = difflib.SequenceMatcher(None, x, y).get_opcodes()
    return sum(1 for tag, *_ in ops if tag != "equal")


def is_sane_normalization(original: str, normalized: str) -> bool:
    """Tolak hasil normalisasi yang panjangnya melenceng jauh (tanda LLM mengarang)."""
    if not normalized or not normalized.strip():
        return False
    ratio = len(normalized) / max(len(original), 1)
    return 0.5 <= ratio <= 1.8


TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "timeout")


def analyze_with_llm(text: str, *, normalize: bool = False, fallback_text: str | None = None,
                     language: str = "Bahasa Indonesia", detail: str = "Standar",
                     examples_k: int | None = None, example_pool: list | None = None,
                     validate_output: bool = True) -> tuple[dict, str, str | None]:
    """Mengembalikan (analisis, engine, model_name). engine: 'llm' atau 'rule'.

    normalize=True  -> LLM juga menormalkan teks; hasilnya ada di analisis["normalized_text"].
    fallback_text   -> teks yang dianalisis bila LLM gagal (mis. hasil normalisasi aturan).
    examples_k      -> jumlah contoh few-shot dari dataset (None = ikut FEWSHOT_K di .env, 0 = mati).
    validate_output -> tambahkan hasil pemeriksaan kualitas otomatis ke catatan analisis.
    """
    import time
    provider = os.environ.get("LLM_PROVIDER", "none").lower()
    callers = {"gemini": _call_gemini, "ollama": _call_ollama, "anthropic": _call_anthropic}

    def finish(analysis, engine, model):
        if validate_output:
            validate.annotate(analysis)
        return analysis, engine, model

    reason = None
    if provider in callers:
        k = int(os.environ.get("FEWSHOT_K", 2)) if examples_k is None else examples_k
        try:
            examples = fewshot.build_examples_text(text, k, example_pool) if k > 0 else ""
        except Exception as exc:  # dataset hilang/rusak tidak boleh menggagalkan analisis
            print(f"[llm_service] contoh few-shot dilewati: {exc!r}")
            examples = ""
        prompt = build_prompt(normalize, language, detail, examples)
        for attempt in (1, 2):
            try:
                raw, model = callers[provider](text, prompt)
                return finish(to_app_format(_parse_json(raw)), "llm", model)
            except Exception as exc:
                reason = f"{type(exc).__name__}: {str(exc)[:200]}"
                print(f"[llm_service] LLM gagal (percobaan {attempt}): {reason}")
                if attempt == 1 and any(k_.lower() in str(exc).lower() for k_ in TRANSIENT):
                    time.sleep(5)  # error sementara (server sibuk / batas kuota): coba sekali lagi
                    continue
                break
    else:
        reason = f"LLM_PROVIDER='{provider}' tidak dikenali atau 'none'"
    analysis = analyze_text(fallback_text or text)
    if reason:
        analysis["notes"].append(f"Alasan LLM tidak terpakai: {reason}")
    return finish(analysis, "rule", None)
