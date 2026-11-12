"""SIKARA - Sistem Identifikasi Kebutuhan, Analisis, dan Rekomendasi Aplikasi
Penjaminan Mutu Polibatam. Seluruh data aplikasi dibaca/ditulis ke MySQL."""

import os
import secrets
import uuid
from datetime import date
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import data  # hanya pemetaan gaya tampilan (warna status/prioritas), bukan data
import db
from llm_service import analyze_with_llm, count_changes, is_sane_normalization
from nlp_utils import extract_text
from normalize import normalize_text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

MAX_TEXT = 5000
MAX_DOC_CHARS = 8000          # batas teks dokumen yang dikirim ke LLM
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
MONTHS_LONG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
               "September", "Oktober", "November", "Desember"]
LANGUAGES = ["Bahasa Indonesia", "English"]
DETAILS = ["Ringkas", "Standar", "Rinci"]
NOTIF_LABELS = [  # label antarmuka; nilai aktif/nonaktif dibaca dari user_settings
    ("done", "Analisis selesai", "Beritahu saya ketika hasil analisis siap ditinjau.", "notify_done"),
    ("email", "Ringkasan lewat email", "Kirim ringkasan mingguan aktivitas proyek.", "notify_email"),
    ("tips", "Tips dari AI", "Tampilkan saran untuk meningkatkan kualitas deskripsi.", "notify_tips"),
]


# ---------- Format tampilan ----------
def fmt_date(dt):
    return f"{dt.day} {MONTHS_SHORT[dt.month - 1]} {dt.year}"


def fmt_size(num_bytes):
    if num_bytes >= 1048576:
        return f"{num_bytes / 1048576:.1f}".replace(".", ",") + " MB"
    return f"{max(1, round(num_bytes / 1024))} KB"


def day_label(d):
    delta = (date.today() - d).days
    if delta == 0:
        return "Hari ini"
    if delta == 1:
        return "Kemarin"
    return f"{d.day} {MONTHS_LONG[d.month - 1]} {d.year}"


def project_view(row):
    source = row["source_type"]
    if row["file_size"]:
        source = f"{source} · {fmt_size(row['file_size'])}"
    return {"id": row["id"], "title": row["title"], "desc": row["description"] or "",
            "source": source, "date": fmt_date(row["created_at"]),
            "status": row["status"], "reqs": int(row["reqs"] or 0)}


def user_view(row):
    parts = row["full_name"].split()
    return {"id": row["id"], "name": row["full_name"], "username": row["username"],
            "role": row["role"], "unit": row["unit"], "email": row["email"],
            "initials": "".join(p[0] for p in parts[:2]).upper() or "?",
            "first_name": parts[0] if parts else row["username"],
            "short_name": (parts[0] + (f" {parts[1][0]}." if len(parts) > 1 else "")) if parts else row["username"]}


# ---------- Sesi ----------
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            return redirect(url_for("login"))
        try:
            row = db.get_user(uid)
        except Exception as exc:
            app.logger.error("Database tidak dapat dihubungi: %r", exc)
            return "Database tidak dapat dihubungi. Pastikan MySQL berjalan, lalu muat ulang halaman.", 503
        if not row:  # akun sudah dihapus
            session.clear()
            return redirect(url_for("login"))
        g.user = user_view(row)
        return view(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    return {"user": getattr(g, "user", None)}


@app.get("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))


@app.route("/masuk", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            conn = db.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, password_hash FROM users WHERE username=%s",
                            (username,))
                row = cur.fetchone()
            conn.close()
        except Exception as exc:
            app.logger.error("Database tidak dapat dihubungi: %r", exc)
            error = "Database tidak dapat dihubungi. Pastikan MySQL berjalan."
        else:
            if not row:
                error = "Nama pengguna tidak dikenali."
            elif not password:
                error = "Kata sandi wajib diisi."
            elif not check_password_hash(row["password_hash"], password):
                error = "Kata sandi salah."
            else:
                session.clear()
                session["user_id"] = row["id"]
                return redirect(url_for("dashboard"))
    return render_template("login.html", page_css="login", error=error, username=username)


@app.get("/keluar")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Halaman ----------
@app.get("/beranda")
@login_required
def dashboard():
    st = db.dashboard_stats(g.user["id"])
    pct = round(st["done"] / st["projects"] * 100) if st["projects"] else 0
    stats = [
        ("folder", "Total proyek", str(st["projects"]), f"+{st['projects_month']} bulan ini"),
        ("document", "Dokumen dianalisis", str(st["documents"]), f"+{st['documents_month']} bulan ini"),
        ("check", "Analisis selesai", str(st["done"]),
         f"{pct}% dari proyek" if st["projects"] else "Belum ada proyek"),
        ("clock", "Sedang diproses", str(st["processing"]),
         "Sedang berjalan" if st["processing"] else "Tidak ada proses berjalan"),
    ]
    recent = [project_view(r) for r in db.list_projects(g.user["id"], limit=4)]
    return render_template("dashboard.html", page_css="dashboard", active="dashboard",
                           stats=stats, recent=recent, status_style=data.STATUS_STYLE)


@app.get("/analisis-baru")
@login_required
def workspace():
    return render_template("workspace.html", page_css="workspace", active="workspace",
                           example_text=db.get_content("example_text"), max_text=MAX_TEXT)


@app.post("/api/analisis")
@login_required
def run_analysis():
    document = None
    input_text = None
    normalized = None

    if request.files.get("file"):  # unggah dokumen (multipart)
        f = request.files["file"]
        name = secure_filename(f.filename or "") or "dokumen"
        ext = Path(name).suffix.lower()
        if ext not in (".pdf", ".docx"):
            return jsonify(error="Format belum didukung. Gunakan PDF atau DOCX."), 400
        path = UPLOAD_DIR / f"{uuid.uuid4().hex[:10]}_{name}"
        f.save(path)
        try:
            doc_text = extract_text(str(path))
        except ImportError as exc:  
            app.logger.error("Paket pembaca dokumen belum terpasang: %r", exc)
            return jsonify(error="Komponen pembaca dokumen belum terpasang di server. "
                                 "Jalankan: pip install python-docx pypdf, lalu jalankan ulang aplikasi."), 500
        except Exception as exc:
            app.logger.error("Gagal membaca dokumen: %r", exc)
            return jsonify(error="Dokumen tidak dapat dibaca. Pastikan file tidak rusak atau terkunci."), 400
        if not doc_text.strip():
            return jsonify(error="Tidak ada teks di dokumen ini (mungkin hasil pindai/gambar)."), 400
        mode, title = "upload", f.filename or name
        text_for_llm = doc_text[:MAX_DOC_CHARS]
        document = {"filename": f.filename or name, "type": ext[1:].upper(),
                    "size": path.stat().st_size, "path": str(path), "text": doc_text}
    else:  # teks langsung (JSON)
        payload = request.get_json(silent=True) or {}
        if payload.get("mode") != "text":
            return jsonify(error="Mode analisis tidak valid."), 400
        title = " ".join(str(payload.get("title", "")).split())[:120]  # rapikan spasi, maks 120
        if not title:
            return jsonify(error="Judul kebutuhan wajib diisi."), 400
        input_text = str(payload.get("text", ""))[:MAX_TEXT]
        if not input_text.strip():
            return jsonify(error="Deskripsi kebutuhan masih kosong."), 400
        normalized = normalize_text(input_text)  # normalisasi aturan = cadangan
        text_for_llm = input_text                # LLM menerima teks asli dan menormalkannya
        mode = "text"

    try:
        prefs = db.get_settings(g.user["id"])
    except Exception as exc:
        app.logger.error("Gagal membaca pengaturan: %r", exc)
        prefs = {"result_language": "Bahasa Indonesia", "detail_level": "Standar"}
    opts = {"language": prefs["result_language"], "detail": prefs["detail_level"]}

    if mode == "text":
        analysis, engine, model = analyze_with_llm(
            text_for_llm, normalize=True, fallback_text=normalized["text"], **opts)
        llm_norm = analysis.pop("normalized_text", None)
        if engine == "llm" and llm_norm and is_sane_normalization(input_text, llm_norm):
            normalized = {"text": llm_norm.strip(),
                          "changes": count_changes(input_text, llm_norm)}
    else:
        analysis, engine, model = analyze_with_llm(text_for_llm, **opts)
        analysis.pop("normalized_text", None)

    try:
        project_id, _ = db.save_analysis(
            g.user["id"], title, mode, analysis, input_text=input_text,
            normalized=normalized, document=document, engine=engine, model_name=model)
    except Exception as exc:
        app.logger.error("Gagal menyimpan ke database: %r", exc)
        return jsonify(error="Hasil analisis tidak dapat disimpan ke database. "
                             "Periksa MySQL lalu coba lagi."), 500
    return jsonify(normalized=normalized, result_url=url_for("result", proyek=project_id))


@app.get("/proyek")
@login_required
def projects():
    items = [project_view(r) for r in db.list_projects(g.user["id"])]
    return render_template("projects.html", page_css="projects", active="projects",
                           projects=items, status_style=data.STATUS_STYLE)


@app.get("/riwayat")
@login_required
def history():
    groups = []
    for r in db.list_activities(g.user["id"]):
        label = day_label(r["created_at"].date())
        entry = (r["icon"], r["title"], r["description"] or "", r["created_at"].strftime("%H.%M"))
        if groups and groups[-1][0] == label:
            groups[-1][1].append(entry)
        else:
            groups.append((label, [entry]))
    return render_template("history.html", page_css="history", active="history", activities=groups)


@app.get("/bantuan")
@login_required
def help_center():
    faqs = [(r["question"], r["answer"]) for r in db.get_faqs()]
    steps = [(r["icon"], r["title"], r["description"]) for r in db.get_help_steps()]
    return render_template("help.html", page_css="help", active="help", faqs=faqs, steps=steps)


@app.get("/pengaturan")
@login_required
def settings():
    s = db.get_settings(g.user["id"])
    notif_rows = [(key, title, desc, bool(s[col])) for key, title, desc, col in NOTIF_LABELS]
    return render_template("settings.html", page_css="settings", active="settings",
                           notif_rows=notif_rows, languages=LANGUAGES, details=DETAILS,
                           pref_language=s["result_language"], pref_detail=s["detail_level"])


@app.get("/profil")
@login_required
def profile():
    st = db.dashboard_stats(g.user["id"])
    return render_template("profile.html", page_css="profile", active="profile", stats=st)


@app.get("/hasil")
@login_required
def result():
    pid = request.args.get("proyek", type=int)
    if not pid:
        return redirect(url_for("workspace"))
    found = db.get_project_result(g.user["id"], pid)
    if not found:
        abort(404)
    title, analysis = found
    total = len(analysis["reqs"]) or 1
    counts = {p: sum(1 for r in analysis["reqs"] if r[3] == p) for p in ("Tinggi", "Sedang", "Rendah")}
    shares = {p: counts[p] / total * 100 for p in counts}
    return render_template("result.html", page_css="result", active="projects",
                           title=title, analysis=analysis, counts=counts, shares=shares,
                           priority_style=data.PRIORITY_STYLE)


# ---------- API: profil, pengaturan, kata sandi ----------
@app.post("/api/profil")
@login_required
def api_profile():
    p = request.get_json(silent=True) or {}
    name, role = str(p.get("name", "")).strip(), str(p.get("role", "")).strip()
    unit, email = str(p.get("unit", "")).strip(), str(p.get("email", "")).strip()
    if not (name and role and unit and email) or "@" not in email:
        return jsonify(error="Nama, jabatan, unit, dan email (valid) wajib diisi."), 400
    try:
        db.update_profile(g.user["id"], name[:100], role[:50], unit[:150], email[:120])
    except Exception as exc:
        app.logger.error("Gagal memperbarui profil: %r", exc)
        msg = "Email sudah dipakai akun lain." if "Duplicate" in str(exc) else "Profil tidak dapat disimpan."
        return jsonify(error=msg), 400
    return jsonify(ok=True, initials=user_view(db.get_user(g.user["id"]))["initials"])


@app.post("/api/pengaturan")
@login_required
def api_settings():
    p = request.get_json(silent=True) or {}
    lang, detail = p.get("language"), p.get("detail")
    if lang not in LANGUAGES or detail not in DETAILS:
        return jsonify(error="Pilihan pengaturan tidak valid."), 400
    try:
        db.save_settings(g.user["id"], bool(p.get("done")), bool(p.get("email")),
                         bool(p.get("tips")), lang, detail)
    except Exception as exc:
        app.logger.error("Gagal menyimpan pengaturan: %r", exc)
        return jsonify(error="Pengaturan tidak dapat disimpan."), 500
    return jsonify(ok=True)


@app.post("/api/kata-sandi")
@login_required
def api_password():
    p = request.get_json(silent=True) or {}
    current, new = str(p.get("current", "")), str(p.get("next", ""))
    if not check_password_hash(db.get_password_hash(g.user["id"]) or "", current):
        return jsonify(error="Kata sandi saat ini salah."), 400
    if len(new) < 8:
        return jsonify(error="Kata sandi baru minimal 8 karakter."), 400
    db.set_password_hash(g.user["id"], generate_password_hash(new))
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG", "1") == "1")
