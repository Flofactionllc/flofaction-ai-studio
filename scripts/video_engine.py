#!/usr/bin/env python3
"""
=============================================================================
FLO FACTION VIDEO ENGINE
HyperFrames Production & Multi-Preset Video Synthesizer
=============================================================================
"""
import os
import sys
import json
import argparse
from pathlib import Path

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
sys.path.append(str(STUDIO_DIR))

from videography.engines.cinematic_engine import BrandVideoEngine

def process_daily_content_plan(script_file=None, demo=False):
    engine = BrandVideoEngine()

    if demo:
        print("🎬 [Video Engine] Running HyperFrames Cinematic Video Preview Demo...")
        engine.render_cinematic_scene(
            prompt="HyperFrames 4K cinematic animation of AI neural networks connecting",
            narration_text="HyperFrames Video Engine preview. Film-grade animation rendering complete.",
            preset="youtube_cinema"
        )
        return

    script_file = script_file or STUDIO_DIR / "daily-content" / "2026-07-25-scripts.json"
    if not Path(script_file).exists():
        print(f"⚠️ Script plan file not found: {script_file}. Generating demo content...")
        from scripts.content_generator import generate_daily_content
        script_file = generate_daily_content()

    with open(script_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scripts = data.get("scripts", data.get("reels", []))
    print(f"📹 [Video Engine] Processing {len(scripts)} scripts from {script_file}...")
    renders = []
    for item in scripts:
        out_f = engine.render_branded_reel(
            product_key=item.get("product", "iul_wealth"),
            platform=item.get("platform", "tiktok"),
            prompt=item.get("visual_prompt", item.get("title", "")),
            narration=item.get("narration", item.get("title", ""))
        )
        if out_f:
            renders.append((item, out_f))

    print(f"✨ Successfully produced {len(renders)} videos!")
    return renders

def main():
    parser = argparse.ArgumentParser(description="Flo Faction HyperFrames Video Production Engine")
    parser.add_argument("--script", type=str, default=None, help="Path to JSON script plan")
    parser.add_argument("--demo", action="store_true", help="Run cinematic preview demo")
    args = parser.parse_args()

    process_daily_content_plan(args.script, args.demo)

if __name__ == "__main__":
    main()