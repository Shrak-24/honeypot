# -*- coding: utf-8 -*-
"""
final_test.py  -  Quick MirrorTrap health check
Run: py final_test.py
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

results = []

def ok(msg):   results.append(('OK  ', msg))
def fail(msg): results.append(('FAIL', msg))

# 1. dotenv
try:
    from dotenv import load_dotenv; ok('python-dotenv installed')
except ImportError:
    fail('python-dotenv NOT installed  ->  pip install python-dotenv')

# 2. App creation
try:
    from mirrortrap.app import create_app
    app = create_app()
    ok('create_app() succeeded')
except Exception as e:
    fail(f'create_app() failed: {e}')
    sys.exit(1)

# 3. Config / env
with app.app_context():
    key = app.config.get('GEMINI_API_KEY','')
    db  = app.config.get('DATABASE_URI','')

if key:
    ok(f'GEMINI_API_KEY loaded ({key[:8]}...)')
else:
    fail('GEMINI_API_KEY is EMPTY - AI endpoints will fail')
ok(f'DATABASE_URI = {db}')

# 4. HTTP endpoints
client = app.test_client()

def hit(method, path, body=None):
    try:
        if method == 'GET':
            r = client.get(path)
        else:
            r = client.post(path, json=body or {})
        j  = r.get_json(silent=True) or {}
        s  = j.get('status', '?')
        if r.status_code < 500:
            ok(f'{method} {path}  =>  {r.status_code} {s}')
        else:
            fail(f'{method} {path}  =>  {r.status_code} {s}  ({j.get("message","")[:80]})')
    except Exception as e:
        fail(f'{method} {path}: {e}')

hit('GET',  '/api/logs')
hit('GET',  '/api/sessions')
hit('GET',  '/api/activity')
hit('GET',  '/api/sessions/sess-aabbcc/commands')
hit('GET',  '/.env')
hit('GET',  '/wp-admin')
hit('POST', '/ai/analyze',            {'limit': 3, 'log_types': ['generic']})
hit('POST', '/ai/generate-fake-data', {'context': 'AWS server'})

# 5. Summary
print('\n' + '='*55)
print('MirrorTrap Health Check Results')
print('='*55)
passed = sum(1 for s,_ in results if s=='OK  ')
failed = sum(1 for s,_ in results if s=='FAIL')
for status, msg in results:
    print(f'  [{status}]  {msg}')
print('='*55)
print(f'  {passed} passed   {failed} failed')
print('='*55)
sys.exit(0 if failed == 0 else 1)
