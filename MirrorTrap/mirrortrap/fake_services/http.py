"""
mirrortrap/fake_services/http.py
──────────────────────────────────
Catch-all fake HTTP service that logs every request and serves lure files
for known sensitive paths.

Fixes applied:
  - ISSUE-5:  Added explicit exclusion guard for /api/, /ai/, and
              /integrations/ prefixes so the catch-all never swallows
              requests meant for real blueprints.
  - ISSUE-14: _classify() now uses path segment matching (split on '/')
              instead of bare substring `in` check to avoid false positives
              like '.env' matching 'get-your-.env-here'.
"""

import os
from flask import Blueprint, request, current_app, Response
from mirrortrap.core.logger import log_attack

fake_http_bp = Blueprint('fake_http_bp', __name__)

# Absolute path to the canary lure files directory
LURES_DIR = os.path.join(os.path.dirname(__file__), 'lures')

# Prefixes that belong to real Flask blueprints — NEVER intercept these.
_REAL_PREFIXES = ('api/', 'ai/', 'integrations/')

# Map of path fragments → (lure filename, attack_type label)
# Keys are matched against individual URL path segments, not substrings.
LURE_MAP = {
    '.env':            ('.env',            'env_exposure_scan'),
    'aws':             ('aws_credentials', 'aws_credentials_scan'),
    '.aws':            ('aws_credentials', 'aws_credentials_scan'),
    'credentials':     ('aws_credentials', 'aws_credentials_scan'),
    'deploy.sh':       ('deploy.sh',       'deploy_script_scan'),
    'db.conf':         ('db.conf',         'db_config_scan'),
    'wp-admin':        (None,              'wordpress_scan'),
    'wp-login':        (None,              'wordpress_scan'),
    'wp-login.php':    (None,              'wordpress_scan'),
    'phpmyadmin':      (None,              'phpmyadmin_scan'),
    'pma':             (None,              'phpmyadmin_scan'),
    'actuator':        (None,              'spring_actuator_scan'),
}


def _read_lure(filename: str) -> str | None:
    """Read and return lure file contents, or None if missing."""
    try:
        with open(os.path.join(LURES_DIR, filename), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def _classify(path: str) -> tuple[str | None, str]:
    """
    Return (lure_filename_or_None, attack_type) for the given URL path.

    Uses segment-based matching: splits path on '/' and checks each segment
    against LURE_MAP keys. This avoids false positives from substring matching
    (e.g. 'get-your-.env-here' no longer matches '.env').
    """
    segments = [seg.lower() for seg in path.split('/') if seg]
    for seg in segments:
        if seg in LURE_MAP:
            return LURE_MAP[seg]
    return None, 'generic_http_scan'


def _handle_fake_request(attack_type: str, lure_content: str | None = None):
    """Log the request and serve either a lure body or a generic 404."""
    payload = {
        "method":  request.method,
        "path":    request.path,
        "headers": dict(request.headers),
        "args":    dict(request.args),
        "form":    dict(request.form),
        "data":    request.get_data(as_text=True)[:2000],  # cap raw body
    }
    db_uri = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    log_attack(
        source_ip=request.remote_addr,
        service='HTTP',
        attack_type=attack_type,
        payload=payload,
        db_uri=db_uri,
    )

    if lure_content:
        # Serve the fake credential file — attacker thinks they found gold
        return Response(lure_content, status=200, mimetype='text/plain')

    return "Not Found\n", 404


@fake_http_bp.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
@fake_http_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def catch_all(path: str):
    """
    Catch-all route.

    1. Skip paths that belong to real Flask blueprints (/api/, /ai/, /integrations/).
    2. For paths matching a known canary lure, serve the fake credential file.
    3. All other paths return a logged 404.
    """
    # ── ISSUE-5 guard: pass through to real blueprints ────────────────────────
    # Flask's own routing ensures real blueprints are matched first when
    # registered before fake_http_bp, but we add an explicit guard here
    # as a defence-in-depth measure.
    path_lower = path.lower().lstrip('/')
    for prefix in _REAL_PREFIXES:
        if path_lower.startswith(prefix) or path_lower == prefix.rstrip('/'):
            # This should never happen in normal Flask routing, but just in case.
            from flask import abort
            abort(404)

    lure_file, attack_type = _classify(path)

    lure_content = None
    if lure_file:
        lure_content = _read_lure(lure_file)

    return _handle_fake_request(attack_type, lure_content)
