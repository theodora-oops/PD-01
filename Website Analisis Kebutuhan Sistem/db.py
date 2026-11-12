"""Koneksi MySQL (phpMyAdmin) dan penyimpanan hasil analisis SIKARA.

Pakai di app.py:
    from db import save_analysis, get_connection
"""
import os

import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "sikara"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def save_analysis(user_id, title, mode, analysis, *, input_text=None,
                  normalized=None, document=None, engine="rule", model_name=None,
                  project_id=None):
    """Simpan satu hasil analisis (format dict dari analyze_text / llm_service).

    document = {"filename":..., "type":"PDF", "size":123, "path":..., "text":...} (opsional)
    Mengembalikan (project_id, analysis_id).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if project_id is None:
                cur.execute(
                    "INSERT INTO projects (user_id, title, description, source_type, status, req_count) "
                    "VALUES (%s,%s,%s,%s,'Selesai',%s)",
                    (user_id, title[:200], (analysis.get("summary") or "")[:500] or None,
                     "Teks" if mode == "text" else document["type"], len(analysis["reqs"])),
                )
                project_id = cur.lastrowid
                src = "input teks" if mode == "text" else f"dokumen {document['type']}"
                cur.execute(
                    "INSERT INTO activities (user_id, project_id, icon, title, description) "
                    "VALUES (%s,%s,'document','Proyek dibuat',%s)",
                    (user_id, project_id, f"{title[:150]} ditambahkan dari {src}."))
            else:
                cur.execute("UPDATE projects SET status='Selesai', req_count=%s WHERE id=%s",
                            (len(analysis["reqs"]), project_id))

            doc_id = None
            if document:
                cur.execute(
                    "INSERT INTO documents (project_id, original_filename, file_type, "
                    "file_size_bytes, stored_path, extracted_text) VALUES (%s,%s,%s,%s,%s,%s)",
                    (project_id, document["filename"], document["type"], document["size"],
                     document.get("path"), document.get("text")),
                )
                doc_id = cur.lastrowid
                size_mb = f"{document['size'] / 1048576:.1f}".replace(".", ",")
                cur.execute(
                    "INSERT INTO activities (user_id, project_id, icon, title, description) "
                    "VALUES (%s,%s,'upload','Dokumen diunggah',%s)",
                    (user_id, project_id, f"{document['filename'][:150]} ({size_mb} MB)"))

            cur.execute(
                "INSERT INTO analyses (project_id, document_id, input_mode, input_text, "
                "normalized_text, normalize_changes, summary, quality_score, engine, model_name) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (project_id, doc_id, mode, input_text,
                 (normalized or {}).get("text"), (normalized or {}).get("changes", 0),
                 analysis["summary"], analysis["score"], engine, model_name),
            )
            aid = cur.lastrowid

            actor_ids = {}
            for i, (name, role, desc) in enumerate(analysis["actors"], 1):
                cur.execute(
                    "INSERT INTO actors (analysis_id, name, role_type, description, sort_order) "
                    "VALUES (%s,%s,%s,%s,%s)", (aid, name, role, desc, i))
                actor_ids[name] = cur.lastrowid

            for code, desc, actor, prio in analysis["reqs"]:
                cur.execute(
                    "INSERT INTO requirements (analysis_id, code, description, actor_id, "
                    "actor_name, priority) VALUES (%s,%s,%s,%s,%s,%s)",
                    (aid, code, desc, actor_ids.get(actor), actor, prio))

            for i, (actor, want, benefit) in enumerate(analysis["stories"], 1):
                cur.execute(
                    "INSERT INTO user_stories (analysis_id, actor_name, want, benefit, sort_order) "
                    "VALUES (%s,%s,%s,%s,%s)", (aid, actor, want, benefit, i))

            for order, (label, css, feats) in enumerate(analysis["features"], 1):
                cur.execute(
                    "INSERT INTO feature_groups (analysis_id, label, css_class, sort_order) "
                    "VALUES (%s,%s,%s,%s)", (aid, label, css, order))
                gid = cur.lastrowid
                for j, name in enumerate(feats, 1):
                    cur.execute(
                        "INSERT INTO feature_items (group_id, name, sort_order) VALUES (%s,%s,%s)",
                        (gid, name, j))

            for note in analysis["notes"]:
                cur.execute("INSERT INTO analysis_notes (analysis_id, note) VALUES (%s,%s)",
                            (aid, note))

            cur.execute(
                "INSERT INTO activities (user_id, project_id, icon, title, description) "
                "VALUES (%s,%s,'check','Analisis selesai',%s)",
                (user_id, project_id, f"{title} menghasilkan {len(analysis['reqs'])} kebutuhan."))
        conn.commit()
        return project_id, aid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_analysis(analysis_id):
    """Ambil kembali analisis dari DB dalam format dict yang sama dengan analyze_text()."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM analyses WHERE id=%s", (analysis_id,))
            a = cur.fetchone()
            if not a:
                return None
            cur.execute("SELECT name, role_type, description FROM actors "
                        "WHERE analysis_id=%s ORDER BY sort_order", (analysis_id,))
            actors = [[r["name"], r["role_type"], r["description"]] for r in cur.fetchall()]
            cur.execute("SELECT code, description, actor_name, priority FROM requirements "
                        "WHERE analysis_id=%s ORDER BY code", (analysis_id,))
            reqs = [[r["code"], r["description"], r["actor_name"], r["priority"]]
                    for r in cur.fetchall()]
            cur.execute("SELECT actor_name, want, benefit FROM user_stories "
                        "WHERE analysis_id=%s ORDER BY sort_order", (analysis_id,))
            stories = [[r["actor_name"], r["want"], r["benefit"]] for r in cur.fetchall()]
            cur.execute("SELECT id, label, css_class FROM feature_groups "
                        "WHERE analysis_id=%s ORDER BY sort_order", (analysis_id,))
            features = []
            for g in cur.fetchall():
                cur.execute("SELECT name FROM feature_items WHERE group_id=%s ORDER BY sort_order",
                            (g["id"],))
                features.append([g["label"], g["css_class"], [r["name"] for r in cur.fetchall()]])
            cur.execute("SELECT note FROM analysis_notes WHERE analysis_id=%s ORDER BY id", (analysis_id,))
            notes = [r["note"] for r in cur.fetchall()]
        return {"summary": a["summary"], "actors": actors, "reqs": reqs, "stories": stories,
                "features": features, "notes": notes, "score": a["quality_score"]}
    finally:
        conn.close()


# ======================================================================
# Fungsi baca/tulis untuk halaman-halaman aplikasi (semua data dari MySQL)
# ======================================================================
def _fetch(sql, params=(), one=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() if one else list(cur.fetchall())
    finally:
        conn.close()


def _write(sql, params=()):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            n = cur.rowcount
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user(user_id):
    return _fetch("SELECT id, username, full_name, role, unit, email FROM users WHERE id=%s",
                  (user_id,), one=True)


def update_profile(user_id, full_name, role, unit, email):
    _write("UPDATE users SET full_name=%s, role=%s, unit=%s, email=%s WHERE id=%s",
           (full_name, role, unit, email, user_id))


def get_password_hash(user_id):
    row = _fetch("SELECT password_hash FROM users WHERE id=%s", (user_id,), one=True)
    return row["password_hash"] if row else None


def set_password_hash(user_id, password_hash):
    _write("UPDATE users SET password_hash=%s WHERE id=%s", (password_hash, user_id))


def get_settings(user_id):
    _write("INSERT IGNORE INTO user_settings (user_id) VALUES (%s)", (user_id,))
    return _fetch("SELECT notify_done, notify_email, notify_tips, result_language, detail_level "
                  "FROM user_settings WHERE user_id=%s", (user_id,), one=True)


def save_settings(user_id, done, email, tips, language, detail):
    _write("UPDATE user_settings SET notify_done=%s, notify_email=%s, notify_tips=%s, "
           "result_language=%s, detail_level=%s WHERE user_id=%s",
           (int(done), int(email), int(tips), language, detail, user_id))


def dashboard_stats(user_id):
    p = _fetch(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(status='Selesai'),0) AS done, COALESCE(SUM(status='Diproses'),0) AS proc, "
        "COALESCE(SUM(YEAR(created_at)=YEAR(CURDATE()) AND MONTH(created_at)=MONTH(CURDATE())),0) AS new_month "
        "FROM projects WHERE user_id=%s", (user_id,), one=True)
    d = _fetch(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(YEAR(d.uploaded_at)=YEAR(CURDATE()) AND MONTH(d.uploaded_at)=MONTH(CURDATE())),0) AS new_month "
        "FROM documents d JOIN projects p ON p.id=d.project_id WHERE p.user_id=%s",
        (user_id,), one=True)
    return {"projects": int(p["total"]), "done": int(p["done"]), "processing": int(p["proc"]),
            "projects_month": int(p["new_month"]),
            "documents": int(d["total"]), "documents_month": int(d["new_month"])}


def list_projects(user_id, limit=None):
    sql = (
        "SELECT p.id, p.title, p.description, p.source_type, p.status, p.created_at, "
        "(SELECT COUNT(*) FROM requirements r WHERE r.analysis_id = "
        "   (SELECT MAX(a.id) FROM analyses a WHERE a.project_id = p.id)) AS reqs, "
        "(SELECT d.file_size_bytes FROM documents d WHERE d.project_id = p.id "
        "   ORDER BY d.id DESC LIMIT 1) AS file_size "
        "FROM projects p WHERE p.user_id=%s ORDER BY p.created_at DESC, p.id DESC")
    params = [user_id]
    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))
    return _fetch(sql, tuple(params))


def list_activities(user_id, limit=200):
    return _fetch("SELECT icon, title, description, created_at FROM activities "
                  "WHERE user_id=%s ORDER BY created_at DESC, id DESC LIMIT %s",
                  (user_id, int(limit)))


def get_faqs():
    return _fetch("SELECT question, answer FROM faqs ORDER BY sort_order, id")


def get_help_steps():
    return _fetch("SELECT icon, title, description FROM help_steps ORDER BY sort_order, id")


def get_content(key, default=""):
    row = _fetch("SELECT content_value FROM app_content WHERE content_key=%s", (key,), one=True)
    return row["content_value"] if row else default


def get_project_result(user_id, project_id):
    """Judul proyek + analisis terbarunya, atau None bila bukan milik pengguna / belum ada."""
    proj = _fetch("SELECT id, title FROM projects WHERE id=%s AND user_id=%s",
                  (project_id, user_id), one=True)
    if not proj:
        return None
    last = _fetch("SELECT MAX(id) AS id FROM analyses WHERE project_id=%s", (project_id,), one=True)
    if not last or not last["id"]:
        return None
    return proj["title"], load_analysis(last["id"])
