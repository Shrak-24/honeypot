"""
mirrortrap/core/logger.py
──────────────────────────
SQLite-backed logging for attack events, SSH sessions, and commands.

Fixes applied:
  - ISSUE-7:  Reuses a single connection per operation via _get_conn() context manager.
  - ISSUE-8:  WAL journal mode enabled in setup_db() for concurrent write safety.
  - ISSUE-20: Robust URI → path extraction via _db_path_from_uri().
"""

import sqlite3
import datetime
import json
import time
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------

def _db_path_from_uri(uri: str) -> str:
    """
    Convert a SQLite URI/path string to a bare filesystem path.

    Handles:
      sqlite:///relative.db     → relative.db
      sqlite:////abs/path.db    → /abs/path.db   (Linux absolute)
      sqlite:///C:/path/db      → C:/path/db     (Windows absolute)
      bare/path.db              → bare/path.db   (already a path)
    """
    if uri.startswith('sqlite:///'):
        return uri[len('sqlite:///'):]
    if uri.startswith('sqlite://'):
        # Two-slash form — unusual but guard it
        return uri[len('sqlite://'):]
    return uri


# ---------------------------------------------------------------------------
# Connection helper — reuse conn with WAL, retry on lock
# ---------------------------------------------------------------------------

@contextmanager
def _get_conn(db_uri: str, retries: int = 5, retry_delay: float = 0.1):
    """
    Context manager that opens a SQLite connection with WAL mode enabled.
    Automatically retries on 'database is locked' up to `retries` times.
    """
    db_path = _db_path_from_uri(db_uri)
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
            return  # success — exit the generator
        except sqlite3.OperationalError as e:
            conn.rollback()
            conn.close()
            if 'locked' in str(e).lower() and attempt < retries:
                last_exc = e
                time.sleep(retry_delay * (2 ** attempt))
                continue   # retry
            raise  # locked but out of retries, or a different OperationalError
        except Exception:
            conn.rollback()
            conn.close()
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------

def setup_db(db_uri: str = 'mirrortrap.db'):
    """Initialize the SQLite database schema. Safe to call multiple times."""
    with _get_conn(db_uri) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute('''
            CREATE TABLE IF NOT EXISTS attack_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                source_ip   TEXT    NOT NULL,
                service     TEXT    NOT NULL,
                attack_type TEXT    NOT NULL,
                payload     TEXT
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS ssh_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL UNIQUE,
                source_ip  TEXT    NOT NULL,
                username   TEXT,
                password   TEXT,
                start_time TEXT    NOT NULL,
                end_time   TEXT,
                success    INTEGER DEFAULT 0
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS ssh_commands (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                timestamp  TEXT    NOT NULL,
                command    TEXT    NOT NULL,
                output     TEXT
            )
        ''')


# ---------------------------------------------------------------------------
# Attack Logs
# ---------------------------------------------------------------------------

def log_attack(source_ip: str, service: str, attack_type: str,
               payload=None, db_uri: str = 'mirrortrap.db'):
    """Log an attack attempt."""
    timestamp = datetime.datetime.utcnow().isoformat()
    if isinstance(payload, dict):
        payload = json.dumps(payload)

    with _get_conn(db_uri) as conn:
        conn.execute(
            'INSERT INTO attack_logs (timestamp, source_ip, service, attack_type, payload) '
            'VALUES (?, ?, ?, ?, ?)',
            (timestamp, source_ip, service, attack_type, payload)
        )


def get_logs(db_uri: str = 'mirrortrap.db', limit: int = 100) -> list:
    """Retrieve the most recent attack logs."""
    with _get_conn(db_uri) as conn:
        cursor = conn.execute(
            'SELECT * FROM attack_logs ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# SSH Session Tracking
# ---------------------------------------------------------------------------

def upsert_session(session_id: str, source_ip: str, username: str = None,
                   password: str = None, success=None, end_time: str = None,
                   db_uri: str = 'mirrortrap.db'):
    """Create or update an SSH session record."""
    with _get_conn(db_uri) as conn:
        cursor = conn.execute(
            'SELECT id FROM ssh_sessions WHERE session_id = ?', (session_id,)
        )
        existing = cursor.fetchone()

        if existing:
            updates, params = [], []
            if username is not None:
                updates.append('username = ?'); params.append(username)
            if password is not None:
                updates.append('password = ?'); params.append(password)
            if success is not None:
                updates.append('success = ?'); params.append(int(success))
            if end_time is not None:
                updates.append('end_time = ?'); params.append(end_time)
            if updates:
                params.append(session_id)
                conn.execute(
                    f"UPDATE ssh_sessions SET {', '.join(updates)} WHERE session_id = ?",
                    params
                )
        else:
            start_time = datetime.datetime.utcnow().isoformat()
            conn.execute(
                'INSERT INTO ssh_sessions '
                '(session_id, source_ip, username, password, start_time, success) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (session_id, source_ip, username, password, start_time,
                 int(success) if success is not None else 0)
            )


def log_command(session_id: str, command: str, output: str = None,
                db_uri: str = 'mirrortrap.db'):
    """Record a command executed during an SSH session."""
    timestamp = datetime.datetime.utcnow().isoformat()
    with _get_conn(db_uri) as conn:
        conn.execute(
            'INSERT INTO ssh_commands (session_id, timestamp, command, output) '
            'VALUES (?, ?, ?, ?)',
            (session_id, timestamp, command, output)
        )


def get_sessions(db_uri: str = 'mirrortrap.db', limit: int = 100,
                 ip_filter: str = None) -> list:
    """Retrieve SSH sessions, optionally filtered by source IP."""
    with _get_conn(db_uri) as conn:
        if ip_filter:
            cursor = conn.execute(
                'SELECT * FROM ssh_sessions WHERE source_ip = ? ORDER BY id DESC LIMIT ?',
                (ip_filter, limit)
            )
        else:
            cursor = conn.execute(
                'SELECT * FROM ssh_sessions ORDER BY id DESC LIMIT ?', (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]


def get_session_commands(session_id: str, db_uri: str = 'mirrortrap.db') -> list:
    """Retrieve all commands captured for a given session."""
    with _get_conn(db_uri) as conn:
        cursor = conn.execute(
            'SELECT * FROM ssh_commands WHERE session_id = ? ORDER BY id ASC',
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_activity_log(db_uri: str = 'mirrortrap.db', limit: int = 200,
                     ip_filter: str = None) -> list:
    """
    Unified view: joins ssh_sessions and ssh_commands to return
    ip_address, command, timestamp, and session_id in one flat list.
    """
    with _get_conn(db_uri) as conn:
        query = '''
            SELECT
                s.source_ip  AS ip_address,
                c.command    AS command,
                c.timestamp  AS timestamp,
                c.session_id AS session_id
            FROM ssh_commands c
            JOIN ssh_sessions s ON c.session_id = s.session_id
        '''
        params: list = []

        if ip_filter:
            query += ' WHERE s.source_ip = ?'
            params.append(ip_filter)

        query += ' ORDER BY c.id DESC LIMIT ?'
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
