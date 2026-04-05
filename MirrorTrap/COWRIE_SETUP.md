# Cowrie SSH Honeypot — Installation & Integration Guide

This guide walks you through installing the **Cowrie SSH honeypot** on a Linux server and connecting it to your **MirrorTrap** Flask backend so that every login attempt, command, and session is captured automatically.

---

## Prerequisites

| Component | Requirement |
|---|---|
| Cowrie host | Linux (Ubuntu/Debian recommended) |
| MirrorTrap host | Python 3.8+, Flask |
| Network | Cowrie must be able to reach MirrorTrap over HTTP |

---

## 1 — Install Cowrie (on the Linux box)

```bash
# Create a dedicated user (recommended)
sudo adduser --disabled-password cowrie
sudo su - cowrie

# Clone the repository
git clone https://github.com/cowrie/cowrie.git
cd cowrie

# Set up a virtual environment
python3 -m venv cowrie-env
source cowrie-env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2 — Configure Cowrie to forward events to MirrorTrap

Copy the default config and edit:

```bash
cp etc/cowrie.cfg.dist etc/cowrie.cfg
nano etc/cowrie.cfg
```

Add / uncomment the **webhook output plugin** section:

```ini
# ── Webhook output (sends JSON events to MirrorTrap) ──────────────
[output_webhooks]
enabled = true
# Point to your MirrorTrap server
url = http://<MIRRORTRAP_IP>:5000/integrations/cowrie/webhook
```

> **Tip:** Replace `<MIRRORTRAP_IP>` with the actual IP or hostname of the machine running `run.py`.

### Optional — redirect port 22 → 2222

Cowrie listens on **port 2222** by default.  
To make it look like a real SSH server on port 22:

```bash
sudo iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
```

---

## 3 — Start Cowrie

```bash
# Inside the cowrie directory with venv activated
bin/cowrie start
```

Check logs:

```bash
tail -f var/log/cowrie/cowrie.log
```

---

## 4 — Start MirrorTrap (on your Flask host)

```bash
cd /path/to/MirrorTrap
pip install -r requirements.txt
python run.py
```

The server listens on `0.0.0.0:5000` by default.

---

## 5 — Test the integration

### Quick smoke test with curl

Simulate a Cowrie login event:

```bash
curl -X POST http://localhost:5000/integrations/cowrie/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "eventid": "cowrie.login.failed",
    "session": "abc123",
    "src_ip": "192.168.1.100",
    "username": "root",
    "password": "toor"
  }'
```

Simulate a command capture:

```bash
curl -X POST http://localhost:5000/integrations/cowrie/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "eventid": "cowrie.command.input",
    "session": "abc123",
    "src_ip": "192.168.1.100",
    "input": "cat /etc/passwd"
  }'
```

Close the session:

```bash
curl -X POST http://localhost:5000/integrations/cowrie/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "eventid": "cowrie.session.closed",
    "session": "abc123",
    "src_ip": "192.168.1.100"
  }'
```

### Verify via API

```bash
# List all sessions
curl http://localhost:5000/api/sessions

# List commands for session abc123
curl http://localhost:5000/api/sessions/abc123/commands

# List generic attack logs
curl http://localhost:5000/api/logs
```

---

## 6 — Real-world test

From **any machine**, SSH into the Cowrie host:

```bash
ssh root@<COWRIE_HOST_IP>
```

Try some commands (`ls`, `whoami`, `cat /etc/shadow`).  
Then check MirrorTrap:

```bash
curl http://<MIRRORTRAP_IP>:5000/api/sessions
curl http://<MIRRORTRAP_IP>:5000/api/sessions/<SESSION_ID>/commands
```

You should see the session with the credentials used and every command captured.

---

## API Reference (quick)

| Endpoint | Method | Description |
|---|---|---|
| `/api/logs` | GET | Generic attack logs |
| `/api/sessions` | GET | SSH sessions (`?ip=`, `?limit=`) |
| `/api/sessions/<id>/commands` | GET | Commands for a session |
| `/integrations/cowrie/webhook` | POST | Cowrie event receiver |
