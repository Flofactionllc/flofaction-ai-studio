#!/usr/bin/env python3
"""
=============================================================================
FLO FACTION TV — BROADCAST ENGINE ASSEMBLY
=============================================================================
Assembles high-end AI Video files with official Canva Intro clips, watermarks,
and platform-specific cropping/padding (9:16 or 16:9).
No basic PIL filters here; this relies entirely on the cinematic output 
of the Cloud AI Video endpoint.
=============================================================================
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
OUT_DIR = STUDIO_DIR / "output" / "broadcast_reels"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = STUDIO_DIR / "output" / "bcast_tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
INTRO_MP4 = STUDIO_DIR / "assets" / "intro" / "canva-flofaction-tv-intro.mp4"
LOGO_PNG = STUDIO_DIR / "assets" / "brand" / "logo-master.png"

class BroadcastAssemblyEngine:
    def __init__(self, platform="reels"):
        self.platform = platform
        # Target resolutions
        if self.platform in ["reels", "tiktok", "shorts"]:
            self.width, self.height = 1080, 1920
        else: # youtube, tv
            self.width, self.height = 1920, 1080

    def assemble_broadcast(self, ai_generated_video_path, output_name="flo_faction_tv_reel.mp4"):
        if not os.path.exists(ai_generated_video_path):
            print(f"⚠️ AI Video not found: {ai_generated_video_path}")
            return None

        out_mp4 = OUT_DIR / output_name

        print("=========================================================================")
        print(f"🎬 [FLO FACTION TV BROADCAST ASSEMBLY ENGINE]")
        print(f"   AI Source Video : {ai_generated_video_path}")
        print(f"   Target Platform : {self.platform} ({self.width}x{self.height})")
        print(f"   Output Reel     : {out_mp4.name}")
        print("=========================================================================")

        # 1. Standardize AI Video format and resolution for the platform
        standard_body = TMP_DIR / "standardized_body.mp4"
        print("🔧 Scaling and padding AI video to broadcast resolution...")
        
        # FFmpeg command to scale and pad to target resolution without distorting the aspect ratio
        scale_filter = f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black"
        
        cmd_scale = [
            "ffmpeg", "-y", "-i", ai_generated_video_path,
            "-vf", scale_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(standard_body)
        ]
        
        subprocess.run(cmd_scale, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Add Watermark if available
        watermarked_body = TMP_DIR / "watermarked_body.mp4"
        if LOGO_PNG.exists():
            print("🌊 Applying Flo Faction TV Network Watermark...")
            # Place watermark in top-right or top-left
            # W=200, H=200 scaled
            watermark_filter = "overlay=W-w-20:20"
            cmd_watermark = [
                "ffmpeg", "-y", "-i", str(standard_body), "-i", str(LOGO_PNG),
                "-filter_complex", f"[1:v]scale=150:-1[wm];[0:v][wm]{watermark_filter}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "copy",
                str(watermarked_body)
            ]
            subprocess.run(cmd_watermark, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            body_to_stitch = watermarked_body
        else:
            body_to_stitch = standard_body

        # 3. Stitch Intro if it exists
        if INTRO_MP4.exists():
            print(f"🎬 Stitching official Canva Flo Faction TV Intro: {INTRO_MP4.name}...")
            
            # First, standardise the intro to EXACTLY the same resolution and codecs as the body
            standard_intro = TMP_DIR / "standardized_intro.mp4"
            cmd_intro_scale = [
                "ffmpeg", "-y", "-i", str(INTRO_MP4),
                "-vf", scale_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-video_track_timescale", "90000",
                str(standard_intro)
            ]
            subprocess.run(cmd_intro_scale, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Re-encode body timescale to match intro for safe concatenation
            safe_body = TMP_DIR / "safe_body.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-i", str(body_to_stitch),
                "-c", "copy", "-video_track_timescale", "90000",
                str(safe_body)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            concat_list = TMP_DIR / "concat.txt"
            with open(concat_list, "w") as f:
                f.write(f"file '{standard_intro.absolute()}'\n")
                f.write(f"file '{safe_body.absolute()}'\n")

            cmd_stitch = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                "-movflags", "+faststart",
                str(out_mp4)
            ]
            
            try:
                subprocess.run(cmd_stitch, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                print(f"[Error] Stitching failed. Using just the body video. Error: {e}")
                out_mp4 = body_to_stitch
        else:
            print("⚠️ Official Canva Intro not found. Proceeding without intro stitching.")
            subprocess.run(["cp", str(body_to_stitch), str(out_mp4)])

        print(f"✨ BROADCAST ASSEMBLY COMPLETE: {out_mp4}")
        return out_mp4

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="AI generated video path")
    parser.add_argument("--platform", type=str, default="reels", help="Target platform (reels, tiktok, youtube, tv)")
    parser.add_argument("--output", type=str, default="flo_faction_tv_reel.mp4", help="Output filename")
    
    args = parser.parse_args()
    engine = BroadcastAssemblyEngine(platform=args.platform)
    engine.assemble_broadcast(args.input, args.output)
