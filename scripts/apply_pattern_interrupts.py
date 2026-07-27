#!/usr/bin/env python3
"""
=============================================================================
FLO FACTION TV NETWORK - PATTERN INTERRUPT ENGINE
=============================================================================
Automatically applies pattern interrupts (e.g. quick cuts, zoom effects,
flash transitions) in the first 3 seconds to enforce the 3-second hook rule
via FFmpeg automation.
=============================================================================
"""

import os
import sys
import subprocess
import argparse

def apply_3s_hook(input_video, output_video):
    """
    Applies a quick 1.2x zoom-in effect during the first 3 seconds to capture attention.
    """
    if not os.path.exists(input_video):
        print(f"[Error] Input video {input_video} not found.")
        return False

    print(f"[Flo Faction TV Network] Applying Pattern Interrupts to {input_video}...")
    
    # FFmpeg filter complex:
    # Uses zoompan for the first 3 seconds, then standard scaling for the rest, concatenating both streams.
    filter_complex = (
        "[0:v]trim=duration=3,zoompan=z='min(zoom+0.0015,1.5)':d=90:s=1080x1920[v1];"
        "[0:v]trim=start=3,setpts=PTS-STARTPTS,scale=1080:1920[v2];"
        "[v1][v2]concat=n=2:v=1:a=0[vout]"
    )
    
    cmd = [
        "ffmpeg", "-y", "-hwaccel", "videotoolbox", "-i", input_video,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "copy",
        output_video
    ]
    
    print("Executing FFmpeg command for 3s hook zoom...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if res.returncode == 0:
        print(f"[SUCCESS] Pattern interrupt applied. Saved to {output_video}")
        return True
    else:
        print(f"[Error] FFmpeg pattern interrupt failed:\n{res.stderr}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pattern Interrupt Engine")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    
    args = parser.parse_args()
    apply_3s_hook(args.input, args.output)
