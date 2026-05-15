"""Cross-platform secret storage.

Primary backend: the OS keychain via :mod:`keyring`. When keyring is
unavailable (headless Linux without a session daemon, sandboxed
environments, broken backends), we transparently fall back to a SQLite
file with Fernet-encrypted values.

Encryption key derivation (fallback only):
    Fernet key = base64( HKDF / SHA-256(
        uuid.getnode() (machine MAC integer) + hardcoded app salt
    ))

This is *not* a defence against an attacker with read access to the user's
disk - it is "obfuscate at rest" while keeping the app zero-config. The
keychain path is always preferred.

Service name: ``"agf-coscientist"``.

Public surface:
    set_secret(key, value)
    get_secret(key) -> str | None
    delete_secret(key)
    list_keys() -> list[str]
    is_using_fallback() -> bool
"""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import threading
import uuid
from typing import Optional

# We deliberately avoid raising at import time so tests can monkey-patch.
try:
    import keyring  # type: ignore
    from keyring.errors import KeyringError  # type: ignore
    _KEYRING_AVAILABLE = True
except Exception:  # pragma: no cover
    keyring = None  # type: ignore
    KeyringError = Exception  # type: ignore
    _KEYRING_AVAILABLE = False

try:
    from cryptography.fernet import Fernet  # type: ignore
    _CRYPTOGRAPHY_AVAILABLE = True
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    _CRYPTOGRAPHY_AVAILABLE = False


SERVICE_NAME = "agf-coscientist"
# 32-byte hardcoded salt -- combined with uuid.getnode() to derive Fernet key.
# Changing this value invalidates all existing fallback-stored secrets.
_APP_SALT = b"agf-coscientist-v1::do-not-rotate-without-migration"

_lock = threading.Lock()
_force_fallback = False  # set by tests to disable keyring


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _keyring_usable() -> bool:
    """Try a no-op probe to see if keyring works on this machine."""
    if _force_fallback:
        return False
    if not _KEYRING_AVAILABLE:
        return False
    try:
        # Avoid mutating anything; just verify a backend is configured.
        kr = keyring.get_keyring()
        backend_name = type(kr).__name__
        # `fail` is the keyring "no backend" sentinel.
        if "fail" in backend_name.lower():
            return False
        return True
    except Exception:
        return False


def _derive_fernet_key() -> bytes:
    if not _CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError(
            "cryptography is not installed - cannot use fallback secret store"
        )
    machine_id = str(uuid.getnode()).encode("utf-8")
    digest = hashlib.sha256(machine_id + b"::" + _APP_SALT).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fallback_db_path() -> str:
    # Imported lazily so tests can monkey-patch the override env var.
    from src.utils.paths import get_secrets_db_path
    return str(get_secrets_db_path())


def _fallback_conn() -> sqlite3.Connection:
    path = _get_fallback_db_path()
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS secrets (
            key TEXT PRIMARY KEY,
            value_encrypted BLOB NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def _fallback_set(key: str, value: str) -> None:
    fernet = Fernet(_derive_fernet_key())
    blob = fernet.encrypt(value.encode("utf-8"))
    conn = _fallback_conn()
    try:
        conn.execute(
            """
            INSERT INTO secrets (key, value_encrypted, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value_encrypted = excluded.value_encrypted,
                updated_at = datetime('now')
            """,
            (key, blob),
        )
        conn.commit()
    finally:
        conn.close()


def _fallback_get(key: str) -> Optional[str]:
    conn = _fallback_conn()
    try:
        row = conn.execute(
            "SELECT value_encrypted FROM secrets WHERE key = ?", (key,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    fernet = Fernet(_derive_fernet_key())
    try:
        return fernet.decrypt(row[0]).decode("utf-8")
    except Exception:
        return None


def _fallback_delete(key: str) -> None:
    conn = _fallback_conn()
    try:
        conn.execute("DELETE FROM secrets WHERE key = ?", (key,))
        conn.commit()
    finally:
        conn.close()


def _fallback_list() -> list[str]:
    conn = _fallback_conn()
    try:
        rows = conn.execute("SELECT key FROM secrets ORDER BY key").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def is_using_fallback() -> bool:
    """Return True iff the encrypted-SQLite fallback is in use."""
    return not _keyring_usable()


def force_fallback(value: bool = True) -> None:
    """Test helper - disables the keyring backend for the current process."""
    global _force_fallback
    _force_fallback = value


def set_secret(key: str, value: str) -> None:
    """Persist ``value`` under ``key``. Overwrites if already present."""
    if not isinstance(value, str):
        raise TypeError("secret value must be a string")
    with _lock:
        if _keyring_usable():
            try:
                keyring.set_password(SERVICE_NAME, key, value)
                _track_key(key)
                return
            except KeyringError:
                pass  # fall through
        _fallback_set(key, value)
        _track_key(key)


def get_secret(key: str) -> Optional[str]:
    """Return the stored secret, or ``None`` if unset."""
    with _lock:
        if _keyring_usable():
            try:
                got = keyring.get_password(SERVICE_NAME, key)
                if got is not None:
                    return got
            except KeyringError:
                pass
        return _fallback_get(key)


def delete_secret(key: str) -> None:
    """Remove ``key``. No-op if it doesn't exist."""
    with _lock:
        if _keyring_usable():
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except Exception:
                pass
        _fallback_delete(key)
        _untrack_key(key)


def list_keys() -> list[str]:
    """List all known keys.

    Keyring backends do not expose enumeration in a portable way, so we
    maintain a small index table inside the fallback DB. Keys written via
    :func:`set_secret` are always tracked; keys written by other means
    will not appear here.
    """
    return _list_tracked_keys()


# ---------------------------------------------------------------------------
# Key index (so we can list_keys even when secrets live in the OS keychain)
# ---------------------------------------------------------------------------


def _index_conn() -> sqlite3.Connection:
    path = _get_fallback_db_path()
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS secret_index (
            key TEXT PRIMARY KEY
        )
        """
    )
    conn.commit()
    return conn


def _track_key(key: str) -> None:
    conn = _index_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO secret_index (key) VALUES (?)", (key,)
        )
        conn.commit()
    finally:
        conn.close()


def _untrack_key(key: str) -> None:
    conn = _index_conn()
    try:
        conn.execute("DELETE FROM secret_index WHERE key = ?", (key,))
        conn.commit()
    finally:
        conn.close()


def _list_tracked_keys() -> list[str]:
    conn = _index_conn()
    try:
        rows = conn.execute(
            "SELECT key FROM secret_index ORDER BY key"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def mask(value: Optional[str], visible: int = 4) -> Optional[str]:
    """Return a redacted preview, eg. 'sk-1234' -> '...1234'.

    Returns ``None`` if ``value`` is None.
    """
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "..." + value[-visible:]
