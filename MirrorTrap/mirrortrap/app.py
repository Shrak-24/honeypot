import os
import sys
from pathlib import Path
from flask import Flask
from flask_cors import CORS

# ── Force UTF-8 stdout/stderr on Windows to prevent charmap codec errors ──────
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Load .env once — run.py already does this before importing create_app,
#    but we keep a lightweight fallback here so the app can also be imported
#    directly (e.g. in tests) without needing run.py.
try:
    from dotenv import load_dotenv
    if not os.getenv('GEMINI_API_KEY'):
        for candidate in [
            Path('.env'),
            Path(__file__).parents[1] / '.env',   # MirrorTrap/.env
            Path(__file__).parents[2] / '.env',   # Hackathon AI/.env
        ]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                print(f"[app.py] Loaded .env from {candidate.resolve()}")
                break
except ImportError:
    pass  # python-dotenv is optional; env vars may already be set

from config import Config
from mirrortrap.core.logger import setup_db

from mirrortrap.api.routes import api_bp
from mirrortrap.integrations.cowrie import cowrie_bp
from mirrortrap.fake_services.http import fake_http_bp
from mirrortrap.ai.routes import ai_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Fix Windows charmap errors: ensure JSON responses are always UTF-8 ──
    # Setting ensure_ascii=False lets Flask emit real Unicode in JSON bodies;
    # Flask still sends the response as UTF-8 bytes, so no codec issue arises.
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # Run startup config validation
    config_class.validate()

    CORS(app, resources={r"/api/*": {"origins": "*"}, r"/ai/*": {"origins": "*"}})

    # Setup the SQLite logger database (idempotent — safe to call every startup)
    setup_db(app.config.get('DATABASE_URI', 'mirrortrap.db'))

    # Register blueprints — order matters: specific routes first, catch-all last
    app.register_blueprint(api_bp,     url_prefix='/api')
    app.register_blueprint(cowrie_bp,  url_prefix='/integrations/cowrie')
    app.register_blueprint(ai_bp,      url_prefix='/ai')

    # Catch-all fake HTTP services MUST be registered last
    app.register_blueprint(fake_http_bp)

    return app
