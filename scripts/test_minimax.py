import os
import requests

HERMES_ENV = "/Users/pauledwards/.hermes/.env"
keys = {}
if os.path.exists(HERMES_ENV):
    for line in open(HERMES_ENV, "r", encoding="utf-8", errors="ignore"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip("\"'\n\r ")

minimax_key = keys.get("MINIMAX_API_KEY")
print("MiniMax Key present:", bool(minimax_key))

headers = {
    "Authorization": f"Bearer {minimax_key}",
    "Content-Type": "application/json"
}

url = "https://api.minimax.chat/v1/video_generation"
payload = {
    "prompt": "3D Pixar animated comedy character with funny shocked expression, 8k resolution",
    "model": "video-01"
}

res = requests.post(url, headers=headers, json=payload)
print("Status:", res.status_code)
print("Response:", res.text[:300])
