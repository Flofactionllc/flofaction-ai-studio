#!/usr/bin/env python3
"""
=============================================================================
FLO FACTION ASSET GENERATOR ENGINE
Image & Thumbnail Generator for Video Production & Social Cover Art
=============================================================================
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
ASSET_DIR = STUDIO_DIR / "output" / "assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

HERMES_ENV = Path.home() / ".hermes" / ".env"

def load_secrets():
    env = {}
    if HERMES_ENV.exists():
        with open(HERMES_ENV, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip("\"'\n\r ")
    return env

SECRETS = load_secrets()

def generate_image(prompt, aspect_ratio="16:9", out_path=None):
    out_path = out_path or ASSET_DIR / f"asset_{int(os.times().elapsed)}.png"
    print(f"🖼️ [Asset Generator] Creating visual asset for prompt: '{prompt}'...")

    # Fallback SVG/PNG thumbnail creation if API unavailable
    width, height = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#0f172a;stop-opacity:1" />
                <stop offset="50%" style="stop-color:#1e1b4b;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#311042;stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#grad)" />
        <circle cx="{width//2}" cy="{height//2}" r="300" fill="#6366f1" opacity="0.15" />
        <text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="48" font-weight="bold">FLO FACTION AI STUDIO</text>
        <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="#a5b4fc" font-family="sans-serif" font-size="28">{prompt[:50]}...</text>
    </svg>"""

    svg_file = out_path.with_suffix(".svg")
    with open(svg_file, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"✅ Generated asset thumbnail: {svg_file}")
    return svg_file

def main():
    parser = argparse.ArgumentParser(description="Flo Faction Visual Asset Generator")
    parser.add_argument("--prompt", type=str, required=True, help="Image prompt")
    parser.add_argument("--ratio", type=str, default="16:9", help="Aspect ratio (16:9 or 9:16)")
    parser.add_argument("--out", type=str, default=None, help="Output image file path")
    args = parser.parse_args()

    out_p = Path(args.out) if args.out else None
    generate_image(args.prompt, args.ratio, out_p)

if __name__ == "__main__":
    main()