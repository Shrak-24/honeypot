"""
mirrortrap/ai/routes.py
────────────────────────
Flask Blueprint exposing two AI-powered endpoints:

  POST /ai/analyze
      Body: { "limit": 50, "ip": "optional-filter" }
      → Pulls logs from SQLite, sends to Gemini, returns attacker profile.

  POST /ai/generate-fake-data
      Body: { "context": "AWS + internal company server" }
      → Asks Gemini to generate dynamic fake credentials for lure files.

Fixes applied:
  - ISSUE-9: Logs are passed through _truncate_logs() in gemini_client
             before embedding in the prompt (handled inside gemini_client).
"""

from flask import Blueprint, request, jsonify, current_app
from mirrortrap.core.logger import get_logs, get_sessions, get_activity_log
from mirrortrap.ai.gemini_client import analyze_logs, generate_fake_data
from mirrortrap.ai.summarizer import build_prompt_summary, estimate_token_reduction

ai_bp = Blueprint('ai_bp', __name__)

# Hard cap on combined log rows sent to Gemini — prevent runaway token usage.
_MAX_LOGS_TO_ANALYZE = 100


def _require_api_key():
    """Return the Gemini API key from app config, or return an error response."""
    key = current_app.config.get('GEMINI_API_KEY', '')
    if not key:
        return None, (
            jsonify({
                "status": "error",
                "message": (
                    "GEMINI_API_KEY is not configured. "
                    "Set the GEMINI_API_KEY environment variable and restart the server."
                )
            }),
            503,
        )
    return key, None


# ── /ai/analyze ─────────────────────────────────────────────────────────────

@ai_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Pull recent honeypot logs from the database and send them to Gemini
    to generate a structured attacker profile.

    Request body (JSON, all optional):
        {
            "limit":      50,               // max log rows per type (default 50)
            "ip":         "10.0.0.1",       // filter logs by attacker IP
            "log_types":  ["activity", "generic"]  // which log tables to include
        }

    Response:
        {
            "status": "success",
            "logs_analyzed": 12,
            "unique_ips_analyzed": 2,
            "token_reduction_pct": 87.3,   // compression savings vs raw logs
            "profile": {
                "attacker_type":       "...",
                "skill_level":         "...",
                "intent":              "...",
                "tools_likely_used":   [...],
                "summary":             "..."
            }
        }
    """
    api_key, err = _require_api_key()
    if err:
        return err

    body      = request.get_json(silent=True) or {}
    limit     = min(int(body.get('limit', 50)), _MAX_LOGS_TO_ANALYZE)
    ip_filter = body.get('ip') or None      # treat empty string as None
    log_types = list(body.get('log_types', ['activity', 'generic']))
    db_uri    = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    combined_logs: list = []

    if 'activity' in log_types:
        combined_logs += get_activity_log(db_uri, limit, ip_filter)

    if 'generic' in log_types:
        generic = get_logs(db_uri, limit)
        if ip_filter:
            generic = [lg for lg in generic if lg.get('source_ip') == ip_filter]
        combined_logs += generic

    # Enforce hard cap after merging both sources
    combined_logs = combined_logs[:_MAX_LOGS_TO_ANALYZE]

    # Pre-compute summary for metadata (summarizer runs again inside analyze_logs
    # but is cheap — pure Python, no I/O)
    summary_meta   = build_prompt_summary(combined_logs)
    reduction_pct  = estimate_token_reduction(combined_logs, summary_meta)
    unique_ips     = summary_meta.get('unique_ips', 0)

    try:
        profile = analyze_logs(combined_logs, api_key)
        return jsonify({
            "status":               "success",
            "logs_analyzed":        len(combined_logs),
            "unique_ips_analyzed":  unique_ips,
            "token_reduction_pct":  reduction_pct,
            "profile":              profile,
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── /ai/generate-fake-data ───────────────────────────────────────────────────

@ai_bp.route('/generate-fake-data', methods=['POST'])
def gen_fake_data():
    """
    Ask Gemini to dynamically generate realistic-but-fake credentials
    tailored to a given attack scenario.

    Request body (JSON):
        {
            "context": "AWS + internal company server running PostgreSQL"
        }

    Response:
        {
            "status": "success",
            "data": {
                "aws_credentials":  { ... },
                "db_credentials":   { ... },
                "env_file":         "...",
                "internal_config":  "...",
                "deploy_script":    "...",
                "explanation":      "..."
            }
        }
    """
    api_key, err = _require_api_key()
    if err:
        return err

    body    = request.get_json(silent=True) or {}
    context = body.get('context', 'AWS + internal company server') or 'AWS + internal company server'

    try:
        fake_data = generate_fake_data(context, api_key)
        return jsonify({"status": "success", "data": fake_data}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
