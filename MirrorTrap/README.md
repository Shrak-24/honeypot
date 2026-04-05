# MirrorTrap 🌐

> **AI-Powered Honeypot Intelligence Platform**  
> Lure attackers. Log everything. Profile them with Gemini AI.

[![GitHub](https://img.shields.io/badge/GitHub-Shrak--24%2Fhoneypot-181717?style=flat&logo=github)](https://github.com/Shrak-24/honeypot)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)
![React](https://img.shields.io/badge/React-Vite-61DAFB?style=flat&logo=react)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-blue?style=flat&logo=google)

---

## What is MirrorTrap?

MirrorTrap is a cybersecurity honeypot system that:

1. **Lures** attackers by exposing fake SSH and HTTP endpoints
2. **Captures** every command, credential attempt, and HTTP payload they send
3. **Profiles** each attacker using Google Gemini AI (skill level, intent, tools used)
4. **Visualizes** all data on a premium real-time SOC dashboard

It was built as a Hackathon project to demonstrate AI-powered threat intelligence.

---

## Features

| Feature | Description |
|---|---|
| 🪤 SSH Honeypot | Captures login attempts, credentials, and shell commands |
| 🌐 HTTP Honeypot | Logs scan attempts, path traversal, exploit probes |
| 🧠 Gemini AI Profiling | Classifies attackers by type, skill, and intent |
| 📊 Live Dashboard | React + Vite SOC dashboard with auto-refresh |
| 🌍 IP Geolocation | Country, city, ISP, proxy/VPN flags |
| ⏱️ Attack Timeline | Per-attacker command and event timeline |
| 🗄️ SQLite Storage | Persistent local database, zero cloud dependency |

---

## Attack Types Detected

- Credential Brute Force & Auth Breach
- Ransomware Staging
- Crypto-Miner Installation
- SQL Injection
- WordPress / CMS Exploit
- ENV / Secrets Exposure (`.env`, AWS credentials)
- Port & Network Scanning
- LFI / Path Traversal
- Botnet C2 Drop
- Lateral Movement / Active Directory attacks

---

## Project Structure

```
MirrorTrap/
├── mirrortrap/            # Flask backend
│   ├── api/routes.py      # REST API endpoints
│   ├── ai/analyzer.py     # Gemini AI profiling
│   ├── core/logger.py     # SQL logging layer
│   └── app.py             # Flask factory
├── dashboard/             # React + Vite frontend
│   └── src/
│       ├── App.jsx        # Main dashboard component
│       └── index.css      # Design system
├── landing/               # Static marketing landing page
│   └── index.html         # Standalone HTML (no build needed)
├── seed.py                # Populate DB with 10 demo attackers
├── run.py                 # Start backend server
└── config.py              # Configuration
```

---

## Quick Start

### 1. Backend

```bash
pip install -r requirements.txt
cp .env.example .env          # Add your GEMINI_API_KEY
py -3 seed.py                 # Seed 10 demo attacker sessions
py -3 run.py                  # Start Flask on :5000
```

### 2. Dashboard

```bash
cd dashboard
npm install
npm run dev                   # Vite dev server → http://localhost:5173
```

### 3. Landing Page

Open `landing/index.html` directly in a browser — no build step needed.

---

## Demo Attackers (Seeded)

| # | IP | Profile | Threat |
|---|---|---|---|
| Attacker 1 | 185.220.101.42 | Brute forcer | Low |
| Attacker 2 | 91.108.4.211 | Credential hunter | **AUTH BREACH** |
| Attacker 3 | 45.142.212.100 | Ransomware staging | Low |
| Attacker 4 | 103.55.38.201 | Crypto-miner | **AUTH BREACH** |
| Attacker 5 | 178.128.23.11 | Port scanner / Tor exit | Low |
| Attacker 6 | 5.188.86.172 | SQL injection | Low |
| Attacker 7 | 162.55.196.130 | APT / Nation-State | **AUTH BREACH** |
| Attacker 8 | 80.211.206.105 | WordPress exploiter | Low |
| Attacker 9 | 192.168.10.55 | Lateral movement | **AUTH BREACH** |
| Attacker 10 | 77.247.108.222 | Botnet C2 dropper | Low |

---

## Tech Stack

- **Backend**: Python 3, Flask, SQLite
- **Frontend**: React, Vite, Vanilla CSS
- **AI**: Google Gemini (Flash model)
- **Geo**: ip-api.com
- **Landing**: Pure HTML/CSS (no framework)

---

## License

MIT — built for educational purposes at a Hackathon.

---

Built with ❤️ by [Shrak-24](https://github.com/Shrak-24)
