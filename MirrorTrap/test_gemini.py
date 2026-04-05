import os, sys
sys.path.insert(0, '.')
os.environ['GEMINI_API_KEY'] = 'AIzaSyD5ZM8WcluQhBZh6wWmy6fuQjSF6BwgW8A'

import google.generativeai as genai
genai.configure(api_key=os.environ['GEMINI_API_KEY'])

# Test gemini-1.5-flash
print("Testing gemini-1.5-flash...")
try:
    m = genai.GenerativeModel("gemini-1.5-flash")
    r = m.generate_content("Say 'hello' in JSON: {\"reply\": \"...\"}")
    print("  OK:", r.text[:100])
except Exception as e:
    print("  FAIL:", str(e)[:200])

# Test gemini-2.0-flash
print("Testing gemini-2.0-flash...")
try:
    m = genai.GenerativeModel("gemini-2.0-flash")
    r = m.generate_content("Say 'hello' in JSON: {\"reply\": \"...\"}")
    print("  OK:", r.text[:100])
except Exception as e:
    print("  FAIL:", str(e)[:200])

# Test gemini-2.0-flash-lite
print("Testing gemini-2.0-flash-lite...")
try:
    m = genai.GenerativeModel("gemini-2.0-flash-lite")
    r = m.generate_content("Say 'hello' in JSON: {\"reply\": \"...\"}")
    print("  OK:", r.text[:100])
except Exception as e:
    print("  FAIL:", str(e)[:200])
