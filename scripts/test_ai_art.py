import os
import requests

HERMES_ENV = "/Users/pauledwards/.hermes/.env"
keys = {}
if os.path.exists(HERMES_ENV):
    for line in open(HERMES_ENV, "r", encoding="utf-8", errors="ignore"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip("\"'\n\r ")

api_key = keys.get("OPENAI_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "dall-e-2",
    "prompt": "High quality 3D Pixar animated comedy character with funny shocked expression, 8k resolution, cinematic lighting",
    "n": 1,
    "size": "1024x1024"
}

res = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
print("Status:", res.status_code)
print("Response:", res.text)
