import os
from pathlib import Path

# ── Load .env (looks in CWD, MirrorTrap dir, and one level up) ────────────
try:
    from dotenv import load_dotenv
    # Search: current dir → script dir → parent dir
    for candidate in [
        Path('.env'),
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / '.env',
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            print(f"[run.py] Loaded .env from {candidate.resolve()}")
            break
except ImportError:
    print("[run.py] WARNING: python-dotenv not installed. Run: pip install python-dotenv")

from mirrortrap.app import create_app
from mirrortrap.fake_services.ssh import start_ssh_honeypot

app = create_app()

# ── Start the built-in SSH honeypot (non-blocking daemon thread) ──────────────
# Controlled by SSH_HONEYPOT_PORT env var (default 2222, set to 0 to disable)
_db_uri = app.config.get('DATABASE_URI', 'mirrortrap.db')
_started = start_ssh_honeypot(db_uri=_db_uri)
if _started:
    import os
    print(f"[run.py] [HONEYPOT] SSH honeypot active on port {os.getenv('SSH_HONEYPOT_PORT', '2222')}")
else:
    print("[run.py] ⚠  SSH honeypot not started — install paramiko or set SSH_HONEYPOT_PORT=0 to suppress.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
