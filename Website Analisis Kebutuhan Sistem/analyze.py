"""Penganalisis lokal berbasis aturan (tanpa LLM): aktor, kebutuhan, user stories, prioritas."""

import re

ACTOR_TERMS = [
    ("administrator", "Admin"), ("admin", "Admin"), ("dokter", "Dokter"),
    ("pasien", "Pasien"), ("apoteker", "Apoteker"), ("perawat", "Perawat"),
    ("dosen", "Dosen"), ("mahasiswa", "Mahasiswa"), ("staf", "Staf"),
    ("kepala", "Kepala"), ("ketua", "Ketua"), ("pimpinan", "Pimpinan"),
    ("direktur", "Direktur"), ("rektor", "Rektor"), ("auditor", "Auditor"),
    ("manajer", "Manajer"), ("manager", "Manajer"), ("pelanggan", "Pelanggan"),
    ("kasir", "Kasir"), ("karyawan", "Karyawan"), ("guru", "Guru"),
    ("siswa", "Siswa"), ("orang tua", "Orang tua"), ("petugas", "Petugas"),
    ("operator", "Operator"), ("penjual", "Penjual"), ("pembeli", "Pembeli"),
    ("tamu", "Tamu"), ("member", "Member"), ("anggota", "Anggota"),
    ("pengurus", "Pengurus"), ("teknisi", "Teknisi"), ("pemilik", "Pemilik"),
    ("pemasok", "Pemasok"), ("supplier", "Pemasok"), ("kurir", "Kurir"),
]

VERBS = sorted(
    [
        "mengelola", "mengatur", "melihat", "mencatat", "mengunggah", "mengunduh",
        "membuat", "memantau", "menyimpan", "mengirim", "menampilkan", "mencetak",
        "melakukan", "memproses", "menyusun", "mencari", "memesan", "membayar",
        "mendaftarkan", "mendaftar", "menjadwalkan", "memeriksa", "memilih", "mengisi",
        "mengubah", "menghapus", "menambahkan", "menambah", "memverifikasi",
        "menyetujui", "menganalisis", "memberikan", "memberi", "mengakses", "menerima",
        "membagikan", "melacak", "mengevaluasi", "melaporkan", "menghitung",
        "mengontrol", "mendata", "mengintegrasikan", "menghubungkan",
    ],
    key=len,
    reverse=True,
)

VERB_PATTERN = re.compile(r"\b(" + "|".join(VERBS) + r")\b", re.I)

BENEFITS = {
    "mengelola": "data terkelola dengan rapi",
    "mengatur": "pengaturan sesuai kebutuhan",
    "melihat": "informasi mudah diakses",
    "mencatat": "tidak ada data yang terlewat",
    "mengunggah": "dokumen tersimpan terpusat",
    "membayar": "transaksi cepat dan aman",
    "memesan": "proses pemesanan lebih mudah",
    "memantau": "perkembangan dapat dipantau",
    "mencari": "informasi cepat ditemukan",
    "menjadwalkan": "jadwal tertata dan tidak bentrok",
    "mendaftar": "proses pendaftaran lebih cepat",
    "melaporkan": "laporan tersedia tepat waktu",
}

HIGH_KEYWORDS = re.compile(
    r"(login|autentik|keamanan|pembayaran|bayar|transaksi|pendaftaran|rekam|data utama|pesan|stok|akun|hak akses|wajib|harus|utama)",
    re.I,
)
LOW_KEYWORDS = re.compile(
    r"(notifikasi|laporan|ekspor|unduh|cetak|tema|komentar|riwayat|pengingat|opsional|tambahan|jika memungkinkan)",
    re.I,
)


def _capitalize(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def detect_actors(text: str) -> list:
    """Daftar aktor [{label, index}] dengan Admin di urutan pertama."""
    found = {}
    for term, label in ACTOR_TERMS:
        match = re.search(rf"\b{term}\b", text, re.I)
        if match and (label not in found or match.start() < found[label]):
            found[label] = match.start()
    actors = [{"label": label, "index": index} for label, index in found.items()]
    actors.sort(key=lambda a: (a["label"] != "Admin", a["index"]))
    return actors


def _priority_for(text: str, sentence: str) -> str:
    if re.search(r"(opsional|jika memungkinkan|tambahan)", sentence, re.I):
        return "Rendah"
    if re.search(r"(wajib|harus|utama|prioritas)", sentence, re.I):
        return "Tinggi"
    if HIGH_KEYWORDS.search(text):
        return "Tinggi"
    if LOW_KEYWORDS.search(text):
        return "Rendah"
    return "Sedang"


def analyze_text(value: str) -> dict:
    text = value.strip()
    actor_list = detect_actors(text)
    fallback_actor = actor_list[0]["label"] if actor_list else "Pengguna"
    items = []

    sentences = []
    for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
        cleaned = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", raw).strip()
        if cleaned:
            sentences.append(cleaned)

    for sentence in sentences:
        first = VERB_PATTERN.search(sentence)
        if not first:
            continue

        subject = detect_actors(sentence[: first.start()])
        sentence_actor = subject[0]["label"] if subject else fallback_actor

        tail = re.sub(r"[.!?]+$", "", sentence[first.start():])
        tail = re.split(
            r"\s+(?:agar|supaya|sehingga|melalui|oleh|karena|yang|untuk)\s+", tail, flags=re.I
        )[0]

        parts = re.split(
            r"\s*,\s*(?:(?:dan|serta|atau)\s+)?|\s+(?:dan|serta|atau|lalu|kemudian)\s+",
            tail,
            flags=re.I,
        )
        current_verb = ""
        for part in parts:
            actor = sentence_actor
            item = part.strip()
            match = VERB_PATTERN.search(item)
            if match:
                prefix_actor = detect_actors(item[: match.start()].strip())
                if prefix_actor:
                    actor = prefix_actor[0]["label"]
                current_verb = match.group(1).lower()
                item = item[match.end():].strip()
            words = item.split()
            if not current_verb or not words or len(words) > 8 or len(item) < 3:
                continue
            if re.fullmatch(r"(sistem|aplikasi|semua|itu|ini|tersebut)", item, re.I):
                continue
            key = f"{current_verb} {item}".lower()
            if any(f"{i['verb']} {i['item']}".lower() == key for i in items):
                continue
            items.append(
                {"verb": current_verb, "item": item, "actor": actor, "sentence": sentence, "raw": False}
            )

    if not items:
        for sentence in sentences:
            if len(sentence.split()) < 4:
                continue
            items.append(
                {
                    "verb": "",
                    "item": re.sub(r"[.!?]+$", "", sentence),
                    "actor": fallback_actor,
                    "sentence": sentence,
                    "raw": True,
                }
            )

    reqs = []
    for index, i in enumerate(items):
        req_id = f"FR-{index + 1:02d}"
        if i["raw"]:
            body = f"Sistem harus memenuhi: {i['item']}."
        else:
            body = f"Sistem memungkinkan {i['actor']} untuk {i['verb']} {i['item']}."
        reqs.append([req_id, body, i["actor"], _priority_for(f"{i['verb']} {i['item']}", i["sentence"])])

    has_auth = re.search(r"(login|autentik|masuk ke|hak akses|kata sandi)", text, re.I)
    if len(actor_list) >= 2 and not has_auth:
        reqs.append(
            [
                f"FR-{len(reqs) + 1:02d}",
                "Sistem menyediakan autentikasi dan pembagian hak akses berdasarkan peran pengguna (saran sistem).",
                actor_list[0]["label"],
                "Tinggi",
            ]
        )

    actor_labels = [a["label"] for a in actor_list] or [fallback_actor]
    actors = []
    for label in actor_labels:
        mine = [i for i in items if i["actor"] == label and not i["raw"]][:2]
        if mine:
            desc = "Terlibat dalam: " + "; ".join(f"{i['verb']} {i['item']}" for i in mine) + "."
        else:
            desc = "Pihak yang berinteraksi dengan sistem."
        actors.append([label, "Pengelola" if label == "Admin" else "Pengguna", desc])

    stories = [
        [i["actor"], f"{i['verb']} {i['item']}", BENEFITS.get(i["verb"], "pekerjaan menjadi lebih efisien")]
        for i in [i for i in items if not i["raw"]][:6]
    ]
    if not stories and items:
        stories.append([items[0]["actor"], items[0]["item"], "kebutuhan terpenuhi oleh sistem"])

    groups = {"Tinggi": [], "Sedang": [], "Rendah": []}
    for index, req in enumerate(reqs):
        if index < len(items):
            i = items[index]
            label = _capitalize(i["item"] if i["raw"] else f"{i['verb']} {i['item']}")
        else:
            label = "Autentikasi dan hak akses"
        groups[req[3]].append(label)
    features = []
    if groups["Tinggi"]:
        features.append(["Harus ada", "bg-brand", groups["Tinggi"]])
    if groups["Sedang"]:
        features.append(["Sebaiknya ada", "bg-brand-soft", groups["Sedang"]])
    if groups["Rendah"]:
        features.append(["Opsional", "bg-line", groups["Rendah"]])

    high = len([r for r in reqs if r[3] == "Tinggi"])
    names = ", ".join(a[0] for a in actors)
    focus = ", ".join(i["item"] for i in items[:3])
    if reqs:
        summary = (
            f"Deskripsi menyebutkan {len(actors)} aktor ({names}) dan menghasilkan "
            f"{len(reqs)} kebutuhan fungsional, {high} di antaranya berprioritas tinggi. "
            f"Fokus utama sistem: {focus}."
        )
    else:
        summary = "Belum ada kebutuhan yang dapat diekstrak dari deskripsi ini."

    notes = []
    if not actor_list:
        notes.append("Belum ada aktor yang disebut jelas. Sebutkan siapa saja pengguna sistem, misalnya admin atau dosen.")
    if len(text) < 150:
        notes.append("Deskripsi masih singkat. Tambahkan tujuan bisnis dan alur utama agar hasil lebih lengkap.")
    has_platform = bool(re.search(r"(web|mobile|android|ios|responsif|desktop)", text, re.I))
    if not has_platform:
        notes.append("Platform belum disebut (web, mobile, atau desktop).")
    has_nfr = bool(
        re.search(r"(keamanan|aman|kinerja|cepat|enkripsi|backup|ketersediaan|skalabil)", text, re.I)
    )
    if not has_nfr:
        notes.append("Kebutuhan non-fungsional (keamanan, kinerja) belum disebut.")
    notes.append("Hasil dibuat dengan analisis berbasis aturan pada teks Anda, bukan LLM. Tinjau kembali sebelum digunakan.")

    score = min(
        95,
        40
        + min(35, len(reqs) * 4)
        + min(10, len(actors) * 3)
        + (5 if has_nfr else 0)
        + (5 if has_platform else 0),
    )

    return {
        "summary": summary,
        "actors": actors,
        "reqs": reqs,
        "stories": stories,
        "features": features,
        "notes": notes,
        "score": score,
    }
