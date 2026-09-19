"""Accounts, sessions, and the audit log for radio-webapp.py.

A "little account system", not a real multi-tenant auth stack: SQLite,
two roles (admin/member), session-cookie login for the web UI, and a
per-user API token (bearer header) for programmatic/cross-site access
that can't rely on cookies. Every mutating request gets logged with who
did it and when, so misuse is visible after the fact rather than needing
to lock down every action up front.

Deployed to /usr/local/bin alongside radio_common.py, radio-webapp.py.
"""
import datetime
import functools
import secrets
import sqlite3

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = "/var/lib/mopidy/radio-users.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                api_token TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT
            )
        """)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_user(row):
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


# --- User management ----------------------------------------------------

def create_user(username, password, role="member"):
    if role not in ("admin", "member"):
        raise ValueError(f"invalid role {role!r}")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, _now()),
        )
        return cur.lastrowid


def verify_user(username, password):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return None
    return _row_to_user(row)


def get_user_by_token(token):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE api_token = ?", (token,)).fetchone()
    return _row_to_user(row)


def get_user_by_id(user_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row)


def get_user_by_username(username):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _row_to_user(row)


def list_users():
    with _connect() as conn:
        rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def set_role(user_id, role):
    if role not in ("admin", "member"):
        raise ValueError(f"invalid role {role!r}")
    with _connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def count_admins():
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()
    return row["n"]


def delete_user(user_id):
    with _connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def generate_token(user_id):
    token = secrets.token_hex(24)
    with _connect() as conn:
        conn.execute("UPDATE users SET api_token = ? WHERE id = ?", (token, user_id))
    return token


def revoke_token(user_id):
    with _connect() as conn:
        conn.execute("UPDATE users SET api_token = NULL WHERE id = ?", (user_id,))


# --- Audit log ------------------------------------------------------------

def log_action(username, action, details=""):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, username, action, details) VALUES (?, ?, ?, ?)",
            (_now(), username, action, details),
        )


def list_audit_log(limit=200):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, username, action, details FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Flask wiring -----------------------------------------------------------

def _authenticate_request():
    """Session cookie first (the web UI), then a bearer token (programmatic
    access - what lets another site call the API without needing
    credentialed cross-origin cookies)."""
    username = session.get("username")
    if username:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is not None:
            return _row_to_user(row)

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return get_user_by_token(auth[len("Bearer "):])

    return None


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user = _authenticate_request()
        if user is None:
            return jsonify({"error": "Login required"}), 401
        g.current_user = user
        response = f(*args, **kwargs)
        if request.method in ("POST", "PUT", "DELETE"):
            body = request.get_json(silent=True)
            log_action(user["username"], f"{request.method} {request.path}", str(body) if body else "")
        return response
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if g.current_user["role"] != "admin":
            return jsonify({"error": "Admins only"}), 403
        return f(*args, **kwargs)
    return wrapper
