from flask import Blueprint, jsonify, current_app, request
from mirrortrap.core.logger import get_logs, get_sessions, get_session_commands, get_activity_log

api_bp = Blueprint('api_bp', __name__)


@api_bp.route('/logs', methods=['GET'])
def get_attack_logs():
    """
    Retrieve generic attack logs.
    Supports optional ?ip= filter to return only logs from a specific source IP,
    and ?limit= to cap the number of returned rows.
    """
    limit     = request.args.get('limit', 100, type=int)
    ip_filter = request.args.get('ip') or None   # treat empty string as None
    db_uri    = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    try:
        logs = get_logs(db_uri, limit)
        if ip_filter:
            logs = [lg for lg in logs if lg.get('source_ip') == ip_filter]
        return jsonify({"status": "success", "data": logs}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List SSH sessions with optional ?ip= and ?limit= filters."""
    limit     = request.args.get('limit', 100, type=int)
    ip_filter = request.args.get('ip')
    db_uri    = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    try:
        sessions = get_sessions(db_uri, limit, ip_filter)
        return jsonify({"status": "success", "data": sessions}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/sessions/<session_id>/commands', methods=['GET'])
def list_session_commands(session_id):
    """List all commands captured during a specific SSH session."""
    db_uri = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    try:
        commands = get_session_commands(session_id, db_uri)
        return jsonify({"status": "success", "data": commands}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/activity', methods=['GET'])
def get_activity():
    """
    Unified activity log: returns ip_address, command, timestamp, session_id
    in a single flat list. Supports ?ip= and ?limit= query params.
    """
    limit     = request.args.get('limit', 200, type=int)
    ip_filter = request.args.get('ip')
    db_uri    = current_app.config.get('DATABASE_URI', 'mirrortrap.db')

    try:
        activity = get_activity_log(db_uri, limit, ip_filter)
        return jsonify({"status": "success", "data": activity}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

