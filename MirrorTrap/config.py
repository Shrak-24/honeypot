import os
import sys
from pathlib import Path

# Anchor to this file's directory so the DB is always next to config.py
# regardless of the working directory Flask is launched from.
_BASE_DIR = Path(__file__).resolve().parent

# ── Environment helpers ────────────────────────────────────────────────────────

def _env(key, default=''):
    return os.getenv(key, default)


class Config:
    # Always use an absolute path so the DB is never created in a surprise CWD.
    _db_raw = _env('DATABASE_URI', f'sqlite:///{_BASE_DIR / "mirrortrap.db"}')
    DATABASE_URI = _db_raw

    SECRET_KEY = _env('SECRET_KEY', '')

    GEMINI_API_KEY = _env('GEMINI_API_KEY', '')

    # Optional: shared secret for Cowrie webhook auth (ISSUE-6)
    COWRIE_WEBHOOK_SECRET = _env('COWRIE_WEBHOOK_SECRET', '')

    # ── Built-in SSH Honeypot settings ────────────────────────────────────────
    # Set SSH_HONEYPOT_PORT=0 to disable the honeypot entirely.
    SSH_HONEYPOT_PORT = int(_env('SSH_HONEYPOT_PORT', '2222'))
    SSH_HONEYPOT_HOST = _env('SSH_HONEYPOT_HOST', '0.0.0.0')
    # Optional path to persist the RSA host key (auto-generated if not set)
    SSH_HOST_KEY_PATH = _env('SSH_HOST_KEY_PATH', '')


    # ── Startup sanity checks ──────────────────────────────────────────────────
    @classmethod
    def validate(cls):
        warnings = []
        if not cls.SECRET_KEY:
            # Generate a random key at runtime so the server can still start,
            # but warn loudly so operators know to set one properly.
            import secrets
            cls.SECRET_KEY = secrets.token_hex(32)
            warnings.append(
                "SECRET_KEY is not set — generated a random ephemeral key. "
                "Set SECRET_KEY in your .env file for stable session handling."
            )
        if not cls.GEMINI_API_KEY:
            warnings.append(
                "GEMINI_API_KEY is not set — AI endpoints will return errors."
            )
        for msg in warnings:
            print(f"[config] ⚠  WARNING: {msg}", file=sys.stderr)
