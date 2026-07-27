import os
import requests

OPENROUTER_KEY = "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"

headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json"
}

url = "https://openrouter.ai/api/v1/chat/completions"
payload = {
    "model": "meta-llama/llama-3.3-70b-instruct",
    "messages": [{"role": "user", "content": "Write a funny 15-second Country Wayne style comedy skit dialogue between two characters."}]
}

res = requests.post(url, headers=headers, json=payload)
print("Status:", res.status_code)
if res.status_code == 200:
    print("✅ OpenRouter API Success!")
    print(res.json()["choices"][0]["message"]["content"][:300])
else:
    print("Response:", res.text[:300])
