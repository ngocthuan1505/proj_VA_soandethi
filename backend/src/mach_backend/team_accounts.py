"""Tài khoản nhóm theo lời mời; không đăng ký công khai hoặc đổi dữ liệu PoC cũ."""

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

SESSION_SECONDS = 8 * 3600


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)


def identity(email, password, name=None):
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]{1,100}@[^\s@]{1,100}\.[^\s@]{1,50}", email):
        raise HTTPException(400, "Nhập email hợp lệ.")
    if not 10 <= len(password) <= 200:
        raise HTTPException(400, "Mật khẩu cần từ 10 đến 200 ký tự.")
    if name is not None and not 1 <= len(name.strip()) <= 100:
        raise HTTPException(400, "Họ tên cần từ 1 đến 100 ký tự.")
    return email


class TeamAccounts:
    def __init__(self, directory: Path, *, clock=time.time):
        directory.mkdir(parents=True, exist_ok=True)
        self.file, self.clock = directory / "accounts.sqlite", clock
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users(
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    salt BLOB NOT NULL, password BLOB NOT NULL, role TEXT NOT NULL
                        CHECK(role IN ('admin','member')));
                CREATE TABLE IF NOT EXISTS sessions(
                    token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS invites(
                    token TEXT PRIMARY KEY, role TEXT NOT NULL, expires INTEGER NOT NULL,
                    email TEXT, used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts(
                    key TEXT PRIMARY KEY, count INTEGER NOT NULL, started INTEGER NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.file, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def invite(self, *, email=None, bootstrap=False):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if bootstrap and db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise HTTPException(409, "Đã có tài khoản; dùng lời mời của quản trị viên.")
            if bootstrap:
                db.execute("DELETE FROM invites WHERE role='admin'")
            db.execute(
                "INSERT INTO invites(token,role,expires,email) VALUES(?,?,?,?)",
                (
                    digest(token),
                    "admin" if bootstrap else "member",
                    int(self.clock()) + 86400,
                    email.strip().lower() if email else None,
                ),
            )
        return token

    @staticmethod
    def public(row):
        return {key: row[key] for key in ("id", "email", "name", "role")}

    def create(self, email, password, name, invite, *, with_session=False):
        email = identity(email, password, name)
        salt, user_id = secrets.token_bytes(16), uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            invitation = db.execute(
                "SELECT * FROM invites WHERE token=? AND used=0 AND expires>?",
                (digest(invite), int(self.clock())),
            ).fetchone()
            if not invitation or invitation["email"] not in (None, email):
                raise HTTPException(400, "Lời mời không đúng, đã dùng hoặc hết hạn.")
            if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                raise HTTPException(409, "Email đã có tài khoản. Hãy đăng nhập.")
            hashed = password_hash(password, salt)
            db.execute(
                "INSERT INTO users VALUES(?,?,?,?,?,?)",
                (user_id, email, name.strip(), salt, hashed, invitation["role"]),
            )
            db.execute("UPDATE invites SET used=1 WHERE token=?", (digest(invite),))
            current = self.public(
                db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            )
            return (current, self.new_session(user_id, db)) if with_session else current

    def login(self, email, password, address, *, with_session=False):
        email = identity(email, password)
        key, now = digest(address + "\0" + email), int(self.clock())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rate = db.execute("SELECT * FROM attempts WHERE key=?", (key,)).fetchone()
            if rate and now - rate["started"] < 600 and rate["count"] >= 10:
                raise HTTPException(429, "Đăng nhập sai nhiều lần. Thử lại sau 10 phút.")
            if not rate or now - rate["started"] >= 600:
                db.execute("INSERT OR REPLACE INTO attempts VALUES(?,1,?)", (key, now))
            else:
                db.execute("UPDATE attempts SET count=count+1 WHERE key=?", (key,))
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        given = password_hash(password, row["salt"] if row else b"\0" * 16)
        if not row or not hmac.compare_digest(given, row["password"]):
            raise HTTPException(401, "Email hoặc mật khẩu chưa đúng.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
            # Không cấp phiên bằng mật khẩu cũ nếu người quản lý vừa reset khi đang băm.
            if not latest or not hmac.compare_digest(row["password"], latest["password"]):
                raise HTTPException(401, "Mật khẩu đã đổi. Hãy đăng nhập lại.")
            db.execute("DELETE FROM attempts WHERE key=?", (key,))
            current = self.public(latest)
            return (current, self.new_session(row["id"], db)) if with_session else current

    def new_session(self, user_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.new_session(user_id, connection)
        token, now = secrets.token_urlsafe(32), int(self.clock())
        db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
        db.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (digest(token), user_id, now + SESSION_SECONDS),
        )
        return token

    def user(self, token):
        if not isinstance(token, str) or len(token) > 100:
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT users.* FROM users JOIN sessions ON users.id=sessions.user_id "
                "WHERE sessions.token=? AND sessions.expires>?",
                (digest(token), int(self.clock())),
            ).fetchone()
            return self.public(row) if row else None

    def logout(self, token):
        if isinstance(token, str):
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token=?", (digest(token),))

    def administrator(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone()
            return self.public(row) if row else None

    def reset_password(self, email, password):
        """Chỉ CLI của người quản lý máy; đổi mật khẩu và thu hồi mọi phiên."""
        email = identity(email, password)
        salt = secrets.token_bytes(16)
        hashed = password_hash(password, salt)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy tài khoản.")
            db.execute("UPDATE users SET salt=?,password=? WHERE id=?", (salt, hashed, row["id"]))
            db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
            db.execute("DELETE FROM attempts")
