"""Accounts and sessions for EnergyGuard.

WHAT THIS IS, AND WHAT IT IS NOT

There was no authentication in this project before. This module adds a real
one — passwords are hashed with PBKDF2 via werkzeug, sessions are server-side
and revocable, tokens are stored as digests — rather than a screen that merely
pretends to check credentials.

It is deliberately small and standalone so it can be swapped for a production
identity provider later without touching anything else.

Be honest about the limits when writing this up:

  * The app is served over plain HTTP in development. A bearer token on the
    wire without TLS can be read by anyone on the network. Put it behind HTTPS
    before it protects anything real.
  * The existing detection APIs (/predict, /transformers, /history …) remain
    open. Guarding them would have meant touching all 29 routes, which is a
    separate change with real breakage risk. Right now authentication gates the
    user interface, not the API surface.
  * There is no email verification and no password reset delivery — the reset
    flow in the UI collects the address and says what would happen.

Additive only: two new tables, its own file. Nothing existing is touched.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from config import DB_PATH


logger = logging.getLogger(__name__)

SESSION_HOURS = 12            # a normal sign-in
REMEMBER_DAYS = 30            # "remember me"
MIN_PASSWORD = 8
MAX_ATTEMPTS = 8              # per email, per window
ATTEMPT_WINDOW = 15 * 60      # seconds

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

# In-memory throttle. Enough to stop casual password guessing; a production
# deployment would use a shared store so it survives a restart and works across
# more than one server process.
_attempts: dict[str, list[float]] = {}


class AuthError(Exception):
    """Something the caller can fix — bad input, wrong password, duplicate email."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
def init_auth_tables() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name     TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash  TEXT NOT NULL UNIQUE,
                user_id     INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                expires_at  REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions (token_hash)")
        connection.commit()
    logger.info("[AUTH] user and session tables ready")


def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(r) for r in connection.execute(query, params).fetchall()]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _clean_email(email: str) -> str:
    email = str(email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    return email


def _check_password(password: str) -> str:
    password = str(password or "")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AuthError("Password must contain at least one letter and one number.")
    return password


def _throttle(email: str) -> None:
    """Reject a burst of failed sign-ins for one address."""
    now = time.time()
    tries = [t for t in _attempts.get(email, []) if now - t < ATTEMPT_WINDOW]
    _attempts[email] = tries
    if len(tries) >= MAX_ATTEMPTS:
        wait = int((ATTEMPT_WINDOW - (now - tries[0])) / 60) + 1
        raise AuthError(f"Too many failed attempts. Try again in about {wait} minutes.", 429)


def _record_failure(email: str) -> None:
    _attempts.setdefault(email, []).append(time.time())


# --------------------------------------------------------------------------- #
# Tokens
#
# The raw token is returned to the client once and never stored. What the
# database keeps is its SHA-256 digest, so a copy of the database does not hand
# an attacker a set of live sessions.
# --------------------------------------------------------------------------- #
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_session(user_id: int, remember: bool) -> tuple[str, float]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + (timedelta(days=REMEMBER_DAYS) if remember
                                else timedelta(hours=SESSION_HOURS))
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_hash_token(token), int(user_id),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), expires.timestamp()),
        )
        # Opportunistic cleanup, so expired rows do not accumulate forever.
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        connection.commit()
    return token, expires.timestamp()


def _public(user: dict[str, Any]) -> dict[str, Any]:
    """Never let the hash leave this module."""
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "created_at": user.get("created_at"),
    }


# --------------------------------------------------------------------------- #
# Public operations
# --------------------------------------------------------------------------- #
def signup(full_name: str, email: str, password: str) -> dict[str, Any]:
    name = str(full_name or "").strip()
    if len(name) < 2:
        raise AuthError("Enter your full name.")
    email = _clean_email(email)
    password = _check_password(password)

    if _rows("SELECT id FROM users WHERE email = ?", (email,)):
        raise AuthError("An account with that email already exists.", 409)

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            "INSERT INTO users (full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.commit()
        user_id = int(cursor.lastrowid)

    token, expires = _issue_session(user_id, remember=False)
    logger.info("[AUTH] account created for %s", email)
    user = _rows("SELECT * FROM users WHERE id = ?", (user_id,))[0]
    return {"user": _public(user), "token": token, "expires_at": expires}


def login(email: str, password: str, remember: bool = False) -> dict[str, Any]:
    email = _clean_email(email)
    _throttle(email)

    rows = _rows("SELECT * FROM users WHERE email = ?", (email,))
    # One message for both "no such user" and "wrong password", so the endpoint
    # cannot be used to discover which addresses have accounts.
    if not rows or not check_password_hash(rows[0]["password_hash"], str(password or "")):
        _record_failure(email)
        raise AuthError("Incorrect email or password.", 401)

    user = rows[0]
    _attempts.pop(email, None)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                           (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
        connection.commit()

    token, expires = _issue_session(user["id"], bool(remember))
    return {"user": _public(user), "token": token, "expires_at": expires}


def user_for_token(token: str) -> dict[str, Any] | None:
    """Resolve a bearer token to a user, or None if absent/expired."""
    if not token:
        return None
    rows = _rows(
        """
        SELECT u.* FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (_hash_token(token), time.time()),
    )
    return _public(rows[0]) if rows else None


def logout(token: str) -> bool:
    if not token:
        return False
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
        connection.commit()
        return bool(cursor.rowcount)


def account_count() -> int:
    try:
        return int(_rows("SELECT COUNT(*) AS n FROM users")[0]["n"])
    except Exception:
        return 0
