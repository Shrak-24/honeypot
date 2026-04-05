"""
mirrortrap/integrations/cowrie.py
──────────────────────────────────
Receives JSON events from a Cowrie SSH honeypot via webhook.

Configure the ``output_webhooks`` section in ``cowrie.cfg`` to point to:
    http://<mirrortrap-host>:<port>/integrations/cowrie/webhook

Set the shared secret in .env:
    COWRIE_WEBHOOK_SECRET=<your-secret>

And in cowrie.cfg add to the webhook output section:
    [output_webhooks]
    url = http://localhost:5000/integrations/cowrie/webhook
    debug = false

Fixes applied:
  - ISSUE-6: Webhook now validates X-Cowrie-Token header against
             COWRIE_WEBHOOK_SECRET config value. Requests without a
             matching token are rejected with HTTP 401.
             If COWRIE_WEBHOOK_SECRET is empty, auth is skipped with a
             startup warning (backwards-compatible default).
"""

import datetime
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app
from mirrortrap.core.logger import log_attack, upsert_session, log_command

cowrie_bp = Blueprint('cowrie_bp', __name__)


# ── Auth helper ─────────────────────────────────────────────────────────────

def _check_webhook_auth() -> bool:
    """
    Validate the X-Cowrie-Token request header against the configured secret.

    Returns True if auth passes (or is disabled because no secret is set).
    Returns False if the token is missing or wrong.
    """
    secret = current_app.config.get('COWRIE_WEBHOOK_SECRET', '')
    if not secret:
        # No secret configured — skip auth (emit warning only on first call
        # to avoid log spam; Flask app startup already warns via config.validate).
        return True

    provided = request.headers.get('X-Cowrie-Token', '')
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).hexdigest(),
        hashlib.sha256(secret.encode()).hexdigest(),
    )


# ── Cowrie event-id handlers ────────────────────────────────────────────────

def _handle_login(event: dict, db_uri: str):
    """Handle cowrie.login.success / cowrie.login.failed events."""
    session_id = event.get('session')
    source_ip  = event.get('src_ip', 'unknown')
    username   = event.get('username')
    password   = event.get('password')
    success    = event.get('eventid') == 'cowrie.login.success'

    upsert_session(
        session_id=session_id,
        source_ip=source_ip,
        username=username,
        password=password,
        success=success,
        db_uri=db_uri,
    )
    return success


def _handle_command(event: dict, db_uri: str):
    """Handle cowrie.command.input / cowrie.command.failed events."""
    session_id = event.get('session')
    command    = event.get('input', event.get('message', ''))

    log_command(
        session_id=session_id,
        command=command,
        output=None,   # Cowrie doesn't include output in the event
        db_uri=db_uri,
    )


def _handle_session_closed(event: dict, db_uri: str):
    """Handle cowrie.session.closed — stamp the end time."""
    session_id = event.get('session')
    source_ip  = event.get('src_ip', 'unknown')
    end_time   = datetime.datetime.utcnow().isoformat()

    upsert_session(
        session_id=session_id,
        source_ip=source_ip,
        end_time=end_time,
        db_uri=db_uri,
    )


# ── Dispatcher map ──────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    'cowrie.login.success':  _handle_login,
    'cowrie.login.failed':   _handle_login,
    'cowrie.command.input':  _handle_command,
    'cowrie.command.failed': _handle_command,
    'cowrie.session.closed': _handle_session_closed,
}


# ── Webhook route ───────────────────────────────────────────────────────────

@cowrie_bp.route('/webhook', methods=['POST'])
def cowrie_webhook():
    """
    Receives JSON events from Cowrie and dispatches to appropriate handlers.
    Requires X-Cowrie-Token header to match COWRIE_WEBHOOK_SECRET (if set).
    """
    # ── Auth check (ISSUE-6) ─────────────────────────────────────────────────
    if not _check_webhook_auth():
        return jsonify({
            "error": "Unauthorized — invalid or missing X-Cowrie-Token header."
        }), 401

    event_data = request.get_json(silent=True)
    if not event_data:
        return jsonify({"error": "No JSON payload provided"}), 400

    event_id  = event_data.get('eventid', 'unknown_cowrie_event')
    source_ip = event_data.get('src_ip', 'unknown')
    db_uri    = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    # Dispatch to a specific handler, fallback to generic attack log
    handler = EVENT_HANDLERS.get(event_id)
    if handler:
        handler(event_data, db_uri)
    else:
        log_attack(
            source_ip=source_ip,
            service='SSH_Cowrie',
            attack_type=f"SSH:{event_id}",
            payload=event_data,
            db_uri=db_uri,
        )

    return jsonify({"status": "logged", "eventid": event_id}), 200
