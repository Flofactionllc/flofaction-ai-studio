#!/usr/bin/env python3
"""
===================================================
FLO FACTION TV — AI ART & SKIT ANIMATOR (FREE TIER)
===================================================
Generates Ultra-High-Quality 3D Pixar / Anime / Cinematic AI Artwork for Skits
USING 100% FREE OPEN-SOURCE TOOLS:
- Stable Diffusion XL (local) for keyframe generation
- Edge-TTS for voiceover
- Wav2Lip for lip-sync (with AnimateDiff fallback)
- FFmpeg for final assembly
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Optional

# Import our free local AI animator
sys.path.append(str(Path(__file__).parent))
from cloud_ai_animator import generate_local_image, generate_local_video, generate_voiceover

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
OUT_AI_DIR = STUDIO_DIR / "output" / "ai_skits"
OUT_AI_DIR.mkdir(parents=True, exist_ok=True)

# Load secrets for any needed tokens (though we're free, we might still need FB token for publishing)
HERMES_ENV = Path.home() / ".hermes" / ".env"
FLOFACTION_ENV = Path.home() / ".flofaction-secrets.env"

def load_secrets():
    env = {}
    for path in [HERMES_ENV, FLOFACTION_ENV]:
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip('"\' \n\r')
    return env

SECRETS = load_secrets()


def generate_wav2lip_lipsync(
    face_image_path: Path,
    audio_path: Path,
    output_path: Path,
    wav2lip_dir: str = "/Users/pauledwards/Wav2Lip"  # Adjust if needed
) -> bool:
    """
    Generate lip-synced video using Wav2Lip.
    Returns True on success, False on failure.
    Assumes Wav2Lip is installed at wav2lip_dir with inference.py and model weights.
    """
    if not face_image_path.exists() or not audio_path.exists():
        print(f"[Wav2Lip] Missing input files: {face_image_path} or {audio_path}")
        return False

    wav2lip_inference = Path(wav2lip_dir) / "inference.py"
    if not wav2lip_inference.exists():
        print(f"[Wav2Lip] ERROR: Wav2Lip not found at {wav2lip_inference}")
        print("[Wav2Lip] Please install Wav2Lip: git clone https://github.com/Rudrabha/Wav2Lip && download wav2lip_gan.pth")
        return False

    # Create temporary directory for Wav2Lip if needed
    temp_dir = Path(wav2lip_dir) / "temp"
    temp_dir.mkdir(exist_ok=True)

    # Build command
    cmd = [
        "python3", str(wav2lip_inference),
        "--checkpoint_path", str(Path(wav2lip_dir) / "wav2lip_gan.pth"),
        "--face", str(face_image_path),
        "--audio", str(audio_path),
        "--outfile", str(output_path),
        "--static", "True",  # For static image input
        "--fps", "25"
    ]

    print(f"[Wav2Lip] Running lip-sync synthesis...")
    print(f"      Command: {' '.join(cmd)}")

    try:
        # Run Wav2Lip
        result = subprocess.run(
            cmd,
            cwd=wav2lip_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            print(f"[Wav2Lip] ERROR: {result.stderr}")
            return False

        if not output_path.exists():
            print(f"[Wav2Lip] ERROR: Output file not created: {output_path}")
            return False

        print(f"[Wav2Lip] ✅ Lip-sync video generated: {output_path}")
        return True

    except subprocess.TimeoutExpired:
        print(f"[Wav2Lip] ERROR: Timeout after 5 minutes")
        return False
    except Exception as e:
        print(f"[Wav2Lip] ERROR: {e}")
        return False


def create_skit_video(
    skit_name: str = "diddy_skit",
    prompt: str = "A funny high-stakes comedy reaction scene between two 3D animated characters in a luxury penthouse studio, vibrant colors, expressive faces",
    narration: str = "Welcome to the Flo Faction TV Network. The premiere autonomous AI and comedy studio.",
    platform: str = "tiktok",
    use_wav2lip: bool = True
) -> Optional[Path]:
    """
    Main pipeline: 
    1. Generate keyframe image (SDXL)
    2. Generate voiceover (Edge-TTS)
    3. Generate lip-sync video (Wav2Lip) OR fallback to animated video (AnimateDiff)
    4. Assemble final reel with optional music bed
    """
    print("=" * 70)
    print(f"🎬 [FLO FACTION TV FREE TIER] Generating AI Skit: {skit_name}")
    print(f"   Prompt: {prompt[:60]}...")
    print(f"   Platform: {platform}")
    print("=" * 70)

    # Step 1: Generate keyframe image using SDXL (via cloud_ai_animator)
    print("\n📝 Step 1: Generating keyframe image with Stable Diffusion XL...")
    keyframe_path = OUT_AI_DIR / f"{skit_name}_keyframe.png"
    if not keyframe_path.exists():
        keyframe_path = generate_local_image(
            prompt=prompt,
            negative_prompt="blurry, deformed, low quality, text, watermark",
            aspect="9:16"
        )
        if not keyframe_path:
            print("❌ Failed to generate keyframe image")
            return None
        # Rename to expected name
        final_keyframe = OUT_AI_DIR / f"{skit_name}_keyframe.png"
        keyframe_path.rename(final_keyframe)
        keyframe_path = final_keyframe
    print(f"   ✅ Keyframe saved: {keyframe_path}")

    # Step 2: Generate voiceover using Edge-TTS (via cloud_ai_animator)
    print("\n🎙️ Step 2: Generating voiceover with Edge-TTS...")
    voiceover_path = OUT_AI_DIR / f"{skit_name}_voiceover.mp3"
    if not voiceover_path.exists():
        voiceover_path = generate_voiceover(
            text=narration,
            voice_id="en-US-AndrewNeural",  # Clear, professional male voice
            output_path=voiceover_path
        )
        if not voiceover_path:
            print("� Failed to generate voiceover")
            return None
    print(f"   ✅ Voiceover saved: {voiceover_path}")

    # Step 3: Generate lip-sync video (Wav2Lip) or fallback to AnimateDiff
    print("\n💬 Step 3: Generating lip-sync video...")
    lipsync_video_path = OUT_AI_DIR / f"{skit_name}_lipsync.mp4"
    
    wav2lip_success = False
    if use_wav2lip:
        print("   Attempting Wav2Lip lip-sync...")
        wav2lip_success = generate_wav2lip_lipsync(
            face_image_path=keyframe_path,
            audio_path=voiceover_path,
            output_path=lipsync_video_path
        )
    
    if not wav2lip_success:
        print("   ⚠️ Wav2Lip failed or disabled. Falling back to AnimateDiff (no lip-sync)...")
        # Generate video directly from prompt using AnimateDiff
        video_path = generate_local_video(
            prompt=prompt,
            negative_prompt="blurry, deformed, low quality, static",
            duration=8  # Match approximate voiceover length
        )
        if not video_path:
            print("❌ Failed to generate fallback video")
            return None
        # Rename to expected lipsync path for consistency path.rename(lipsync_video_path)
        print(f"   ✅ Fallback video generated: {lipsync_video_path}")
    else:
        print(f"   ✅ Lip-sync video generated: {lipsync_video_path}")

    # Step 4: Assemble final reel with music bed and loudnorm (optional)
    print("\n🎥 Step 4: Assembling final reel...")
    music_path = STUDIO_DIR / "assets" / "music" / "background.mp3"
    if not music_path.exists():
        music_path = None
        print("   ⚠️ No music bed found, proceeding without music")

    # Determine output path based on platform
    platform_specs = {
        "tiktok": (1080, 1920, 180),
        "youtube_shorts": (1080, 1920, 60),
        "instagram_reels": (1080, 1920, 90)
    }
    res, max_dur = platform_specs.get(platform, (("1080x1920", 60)))
    w, h = map(int, res.split("x"))

    final_output = OUT_AI_DIR / f"{skit_name}_final_{platform}.mp4"

    # FFmpeg filtergraph: scale/pad + audio mix (voice + music ducking) + loudnorm
    filter_complex = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[vout];"
        f"[1:a]volume=1.0,aloudnorm=I=-14:TP=-1:LRA=11[voice];"
    )

    if music_path and music_path.exists():
        filter_complex += (
            f"[2:a]volume=-18dB,aloudnorm=I=-24:TP=-3:LRA=7[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=3,"
            f"aloudnorm=I=-14:TP=-1:LRA=11[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(lipsync_video_path),
            "-i", str(voiceover_path),
            "-i", str(music_path),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(max_dur),
            "-movflags", "+faststart",
            str(final_output)
        ]
    else:
        filter_complex += "[voice]aloudnorm=I=-14:TP=-1:LRA=11[aout]"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(lipsync_video_path),
            "-i", str(voiceover_path),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(max_dur),
            "-movflags", "+faststart",
            str(final_output)
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"   ⚠️ FFmpeg warning: {result.stderr[:200]}")
        # Even if ffmpeg warns, check if output exists
        if final_output.exists():
            print(f"   ✅ Final reel assembled: {final_output}")
            return final_output
        else:
            print(f"   ❌ FFmpeg failed to produce output")
            return None
    except Exception as e:
        print(f"   ❌ Error during assembly: {e}")
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FLO FACTION TV — AI ART & SKIT ANIMATOR")
    parser.add_argument("--skit", type=str, default="diddy_skit", help="Sketch name (matches audio file)")
    parser.add_argument("--style", type=str, default="cinematic", help="Style prompt modifier")
    parser.add_argument("--prompt", type=str, default="A funny high-stakes comedy reaction scene between two 3D animated characters in a luxury penthouse studio, vibrant colors, expressive faces", help="Base prompt for keyframe generation")
    parser.add_argument("--narration", type=str, default="Welcome to the Flo Faction TV Network. The premiere autonomous AI and comedy studio.", help="Voiceover narration text")
    parser.add_argument("--platform", type=str, default="tiktok", choices=["tiktok", "youtube_shorts", "instagram_reels"], help="Target platform for final reel")
    parser.add_argument("--no-wav2lip", action="store_true", dest="no_wav2lip", help="Disable Wav2Lip lip-sync (use only if Fal.ai unavailable)")
    args = parser.parse_args()
    
    result = create_skit_video(
        skit_name=args.skit,
        prompt=args.prompt,
        narration=args.narration,
        platform=args.platform,
        use_wav2lip=not args.no_wav2lip
    )
    
    if result:
        print(f"\n🎉 SUCCESS: {result}")
    else:
        print("\n❌ FAILED")
        sys.exit(1)
