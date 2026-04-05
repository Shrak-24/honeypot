"""
test_app.py - Comprehensive test for MirrorTrap
Run: py test_app.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("MirrorTrap Diagnostic Test")
print("=" * 60)

# ── 1. Check .env loading ────────────────────────────────────
print("\n[1] Checking .env / environment...")
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
env_path = os.path.abspath(env_path)
if os.path.exists(env_path):
    print(f"  .env found at: {env_path}")
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print("  python-dotenv loaded .env")
    except ImportError:
        # Manually parse
        print("  python-dotenv not installed — loading manually")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
else:
    print(f"  .env NOT found at: {env_path}")

gemini_key = os.environ.get('GEMINI_API_KEY', '')
secret_key = os.environ.get('SECRET_KEY', '')
print(f"  GEMINI_API_KEY: {'SET (' + gemini_key[:8] + '...)' if gemini_key else 'NOT SET'}")
print(f"  SECRET_KEY: {'SET' if secret_key else 'NOT SET'}")

# ── 2. Import checks ─────────────────────────────────────────
print("\n[2] Testing imports...")

def test_import(module_path, what=None):
    try:
        if what:
            mod = __import__(module_path, fromlist=[what])
            getattr(mod, what)
        else:
            __import__(module_path)
        print(f"  [OK]   {module_path}" + (f".{what}" if what else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {module_path}: {e}")
        return False

test_import("flask")
test_import("flask_cors")
test_import("google.generativeai")
test_import("mirrortrap.core.logger")
test_import("mirrortrap.core.logger", "setup_db")
test_import("mirrortrap.core.logger", "get_logs")
test_import("mirrortrap.core.logger", "get_sessions")
test_import("mirrortrap.core.logger", "get_activity_log")
test_import("mirrortrap.ai.gemini_client", "analyze_logs")
test_import("mirrortrap.ai.gemini_client", "generate_fake_data")
test_import("mirrortrap.api.routes", "api_bp")
test_import("mirrortrap.ai.routes", "ai_bp")
test_import("mirrortrap.integrations.cowrie", "cowrie_bp")
test_import("mirrortrap.fake_services.http", "fake_http_bp")

# ── 3. App creation ──────────────────────────────────────────
print("\n[3] Creating Flask app...")
try:
    from mirrortrap.app import create_app
    app = create_app()
    print("  [OK]   create_app()")
    print("  Routes registered:")
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        methods = ','.join(sorted(m for m in rule.methods if m not in ('HEAD','OPTIONS')))
        print(f"         {rule.rule:50s}  [{methods}]")
except Exception as e:
    print(f"  [FAIL] create_app: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── 4. Config / API key in app ───────────────────────────────
print("\n[4] Checking app config...")
with app.app_context():
    key = app.config.get('GEMINI_API_KEY', '')
    db  = app.config.get('DATABASE_URI', '')
    print(f"  GEMINI_API_KEY in config: {'YES (' + key[:8] + '...)' if key else 'NO — will fail AI calls'}")
    print(f"  DATABASE_URI: {db}")

# ── 5. Database ──────────────────────────────────────────────
print("\n[5] Testing database...")
try:
    from mirrortrap.core.logger import setup_db, get_logs, get_sessions, get_activity_log
    db_uri = app.config.get('DATABASE_URI', 'mirrortrap.db')
    setup_db(db_uri)
    logs     = get_logs(db_uri, 5)
    sessions = get_sessions(db_uri, 5)
    activity = get_activity_log(db_uri, 5)
    print(f"  [OK]   DB accessible at {db_uri}")
    print(f"         attack_logs rows (sample 5): {len(logs)}")
    print(f"         ssh_sessions rows (sample 5): {len(sessions)}")
    print(f"         activity rows (sample 5): {len(activity)}")
except Exception as e:
    print(f"  [FAIL] DB: {e}")
    import traceback; traceback.print_exc()

# ── 6. Flask test client endpoints ───────────────────────────
print("\n[6] Testing HTTP endpoints...")

client = app.test_client()

def hit(method, path, json=None, label=None):
    label = label or f"{method} {path}"
    try:
        if method == 'GET':
            resp = client.get(path)
        else:
            resp = client.post(path, json=json or {})
        data = resp.get_json(silent=True)
        status_ok = resp.status_code < 500
        msg = f"  {'[OK]  ' if status_ok else '[FAIL]'} {label} → {resp.status_code}"
        if data and 'status' in data:
            msg += f" ({data['status']})"
        print(msg)
        if not status_ok and data:
            print(f"         detail: {data}")
        return resp
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")

hit('GET',  '/api/logs')
hit('GET',  '/api/sessions')
hit('GET',  '/api/activity')
hit('GET',  '/api/sessions/sess-aabbcc/commands')
hit('POST', '/ai/analyze',            json={"limit": 5})
hit('POST', '/ai/generate-fake-data', json={"context": "AWS server"})
hit('GET',  '/.env',                  label='GET /.env (lure)')
hit('GET',  '/wp-admin',              label='GET /wp-admin (lure)')
hit('GET',  '/phpmyadmin',            label='GET /phpmyadmin (lure)')

print("\n" + "=" * 60)
print("Diagnostics complete.")
print("=" * 60)
