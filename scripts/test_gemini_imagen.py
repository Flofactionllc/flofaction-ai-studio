import os
import requests
import json

GEMINI_KEY = "AIzaSyByEvi5-zYjO5xKQIwdgjV17_LLq0NF9OQ"

url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_KEY}"

headers = {"Content-Type": "application/json"}
payload = {
    "instances": [
        {"prompt": "High-end 3D Pixar animated comedy skit keyframe, relatable funny facial expression, luxury penthouse, 8k resolution, cinematic lighting"}
    ],
    "parameters": {
        "sampleCount": 1,
        "aspectRatio": "9:16"
    }
}

res = requests.post(url, headers=headers, json=payload)
print("Status:", res.status_code)
if res.status_code == 200:
    print("✅ Gemini Imagen 3 API Success!")
    data = res.json()
    img_b64 = data["predictions"][0]["bytesBase64Encoded"]
    import base64
    out_path = "/Users/pauledwards/flofaction-ai-studio/output/ai_skits/gemini_imagen_test.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(img_b64))
    print(f"Saved AI image: {out_path}")
else:
    print("Response:", res.text[:300])
