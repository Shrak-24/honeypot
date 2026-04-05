"""
mirrortrap/ai/summarizer.py
────────────────────────────
Pre-Gemini log compression pipeline.

Converts raw MirrorTrap log rows into a compact structured summary
that preserves all analytical value while stripping noise (raw headers,
full payloads, duplicate rows).

Token reduction target: ≥ 70% vs sending raw logs.

Pipeline:
  1. Group all log rows by attacker IP
  2. Per-IP: count events, tally attack-type frequencies, extract
     shell commands, identify credential patterns
  3. Emit a single compact summary dict — NOT the raw rows

Public API
----------
  build_prompt_summary(logs: list[dict]) -> dict
      Takes mixed log rows (activity / attack_logs / combined) and
      returns the compact summary ready to be JSON-serialised into a prompt.

  estimate_token_reduction(original_logs: list, summary: dict) -> float
      Returns the estimated % reduction in serialised character count.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants — what to KEEP vs DISCARD from each log row
# ---------------------------------------------------------------------------

# Fields we explicitly DROP because they're noisy (headers, raw body, etc.)
_DROP_FIELDS = frozenset({
    'headers', 'data', 'form', 'args',  # HTTP request noise
    'id',                                # DB auto-increment — irrelevant to AI
    'output',                            # Cowrie command output (usually empty)
})

# SSH command patterns that reveal attacker intent — extract these explicitly
_RECON_PATTERNS = re.compile(
    r'\b(uname|id|whoami|hostname|ifconfig|ip addr|netstat|ps aux|env|'
    r'cat /etc/passwd|cat /etc/shadow|ls -la|find /|wget|curl|chmod|'
    r'crontab|scp|ssh|nmap|masscan|python|perl|bash|sh |\.\/)\b',
    re.IGNORECASE,
)

# AWS/credential hunting command patterns
_CRED_PATTERNS = re.compile(
    r'\b(aws|credentials|\.env|secret|password|key|token|\.aws|'
    r'config|shadow|sudoers|\.ssh|authorized_keys)\b',
    re.IGNORECASE,
)

# Download / execution patterns (malware staging)
_EXEC_PATTERNS = re.compile(
    r'\b(wget|curl|fetch|nc |netcat|mkfifo|/tmp/|/dev/shm|chmod [0-9]|'
    r'base64|eval|exec|python -c|perl -e|bash -i)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _classify_command(cmd: str) -> list[str]:
    """Return a list of intent labels inferred from a shell command."""
    labels = []
    if _CRED_PATTERNS.search(cmd):
        labels.append('credential_hunting')
    if _EXEC_PATTERNS.search(cmd):
        labels.append('malware_execution')
    if _RECON_PATTERNS.search(cmd):
        labels.append('reconnaissance')
    return labels or ['other']


def _parse_ts(ts_str: str | None) -> datetime | None:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    if not ts_str:
        return None
    try:
        s = ts_str if ts_str.endswith('Z') else ts_str + 'Z'
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Per-IP aggregator
# ---------------------------------------------------------------------------

def _aggregate_by_ip(logs: list[dict]) -> dict[str, dict]:
    """
    Group raw log rows by attacker IP and aggregate into a per-IP profile.

    Returns a dict keyed by IP address, each value being a profile dict.
    """
    by_ip: dict[str, dict] = defaultdict(lambda: {
        'ip': '',
        'total_events': 0,
        'attack_type_freq': defaultdict(int),   # {attack_type: count}
        'ssh_commands': [],                      # unique commands seen
        'command_intents': defaultdict(int),     # {intent_label: count}
        'login_attempts': 0,
        'successful_logins': 0,
        'services_hit': set(),
        'usernames_tried': set(),
        'passwords_tried': set(),
        'timestamps': [],
    })

    seen_commands: dict[str, set] = defaultdict(set)  # ip → set of commands

    for row in logs:
        # Resolve the IP — activity log uses 'ip_address', others use 'source_ip'
        ip = row.get('ip_address') or row.get('source_ip') or 'unknown'
        bucket = by_ip[ip]
        bucket['ip'] = ip
        bucket['total_events'] += 1

        # Attack type tallying
        atype = row.get('attack_type')
        if atype:
            bucket['attack_type_freq'][atype] += 1

        # Service
        svc = row.get('service')
        if svc:
            bucket['services_hit'].add(svc)

        # SSH command extraction (from activity log rows)
        cmd = row.get('command')
        if cmd and cmd not in seen_commands[ip]:
            seen_commands[ip].add(cmd)
            bucket['ssh_commands'].append(cmd)
            for intent in _classify_command(cmd):
                bucket['command_intents'][intent] += 1

        # Timestamp tracking for session duration
        ts = _parse_ts(row.get('timestamp'))
        if ts:
            bucket['timestamps'].append(ts)

        # Login tracking (from session rows)
        if 'login' in (atype or '').lower() or row.get('username'):
            bucket['login_attempts'] += 1
            if row.get('success') == 1 or row.get('success') is True:
                bucket['successful_logins'] += 1
            uname = row.get('username')
            passwd = row.get('password')
            if uname:
                bucket['usernames_tried'].add(uname)
            if passwd:
                bucket['passwords_tried'].add(passwd)

    return dict(by_ip)


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_prompt_summary(logs: list[dict]) -> dict:
    """
    Convert raw log rows into a compact structured summary for Gemini.

    Structure returned:
    {
      "total_events"  : int,
      "unique_ips"    : int,
      "time_window"   : {"start": ISO, "end": ISO, "duration_minutes": float},
      "attackers": [
        {
          "ip"                : "1.2.3.4",
          "event_count"       : int,
          "services_targeted" : ["HTTP", "SSH_Cowrie"],
          "attack_types"      : {"env_exposure_scan": 3, ...},
          "top_attack_type"   : "env_exposure_scan",
          "command_count"     : int,
          "unique_commands"   : ["uname -a", ...],   # max 10
          "command_intents"   : {"reconnaissance": 4, "credential_hunting": 2},
          "login_attempts"    : int,
          "successful_logins" : int,
          "credential_combos" : int,   # unique user/pass pairs tried
          "active_minutes"    : float  # session active duration
        },
        ...
      ]
    }
    """
    if not logs:
        return {"total_events": 0, "unique_ips": 0, "attackers": []}

    aggregated = _aggregate_by_ip(logs)

    # Global time window
    all_ts = []
    for bucket in aggregated.values():
        all_ts.extend(bucket['timestamps'])

    time_window: dict = {}
    if all_ts:
        all_ts.sort()
        start, end = all_ts[0], all_ts[-1]
        duration_m = (end - start).total_seconds() / 60
        time_window = {
            "start": start.isoformat(),
            "end":   end.isoformat(),
            "duration_minutes": round(duration_m, 1),
        }

    attackers = []
    for ip, bucket in sorted(
        aggregated.items(),
        key=lambda kv: kv[1]['total_events'],
        reverse=True,
    ):
        # Compute active duration per attacker
        ts_list = bucket['timestamps']
        active_m = 0.0
        if len(ts_list) >= 2:
            ts_list.sort()
            active_m = round((ts_list[-1] - ts_list[0]).total_seconds() / 60, 1)

        # Top attack type
        freq = dict(bucket['attack_type_freq'])
        top_atype = max(freq, key=freq.get) if freq else None

        # Credential combinations tried
        cred_combos = max(len(bucket['usernames_tried']), len(bucket['passwords_tried']))

        attackers.append({
            "ip":                 ip,
            "event_count":        bucket['total_events'],
            "services_targeted":  sorted(bucket['services_hit']),
            "attack_types":       freq,
            "top_attack_type":    top_atype,
            "command_count":      len(bucket['ssh_commands']),
            "unique_commands":    bucket['ssh_commands'][:10],   # cap at 10
            "command_intents":    dict(bucket['command_intents']),
            "login_attempts":     bucket['login_attempts'],
            "successful_logins":  bucket['successful_logins'],
            "credential_combos":  cred_combos,
            "active_minutes":     active_m,
        })

    return {
        "total_events": len(logs),
        "unique_ips":   len(aggregated),
        "time_window":  time_window,
        "attackers":    attackers,
    }


# ---------------------------------------------------------------------------
# Token reduction estimator
# ---------------------------------------------------------------------------

def estimate_token_reduction(original_logs: list, summary: dict) -> float:
    """
    Estimate the percentage reduction in character count (proxy for tokens).

    Returns a float in [0, 100] representing the % saved.
    """
    original_chars = len(json.dumps(original_logs))
    summary_chars  = len(json.dumps(summary))
    if original_chars == 0:
        return 0.0
    reduction = (1 - summary_chars / original_chars) * 100
    return round(max(0.0, reduction), 1)
