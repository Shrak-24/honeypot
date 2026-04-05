import os, sys
sys.path.insert(0, '.')
os.environ['GEMINI_API_KEY'] = 'AIzaSyD5ZM8WcluQhBZh6wWmy6fuQjSF6BwgW8A'

import google.generativeai as genai
genai.configure(api_key=os.environ['GEMINI_API_KEY'])

print("Available models that support generateContent:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"  {m.name}")
