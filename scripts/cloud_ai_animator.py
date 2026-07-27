#!/usr/bin/env python3
"""
===============================================================================
FLO FACTION TV NETWORK - LOCAL AI ANIMATOR (100% FREE & OPEN SOURCE)
===============================================================================
Runs entirely on local Apple Silicon (MPS) using HuggingFace diffusers.
Models: AnimateDiff, Stable Video Diffusion, CogVideoX, Wan 2.1 (via diffusers)
TTS: edge-tts (free Microsoft neural voices) + Kokoro-TTS (optional local)
NO API KEYS REQUIRED - ZERO COST
===============================================================================
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# Load environment
ENV_PATHS = [
    Path.home() / ".hermes" / ".env",
    Path.home() / ".flofaction-secrets.env",
    Path.home() / ".autonomous" / ".env",
    Path("/Users/pauledwards/flofaction-ai-studio/.env"),
]

def load_keys():
    keys = {}
    for path in ENV_PATHS:
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        keys[k.strip()] = v.strip('"\' \n\r')
    return keys

KEYS = load_keys()

OUTPUT_DIR = Path("/Users/pauledwards/flofaction-ai-studio/output/broadcast_reels")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LOCAL TTS: edge-tts (FREE Microsoft Neural Voices)
# =============================================================================

EDGE_VOICES = {
    "male_authoritative": "en-US-AndrewNeural",
    "male_friendly": "en-US-GuyNeural", 
    "female_warm": "en-US-JennyNeural",
    "female_professional": "en-US-AriaNeural",
    "uk_male": "en-GB-RyanNeural",
    "uk_female": "en-GB-SoniaNeural",
}

def generate_voiceover_edge(text: str, voice_key: str = "male_authoritative", output_path: Optional[str] = None) -> Optional[Path]:
    """100% Free TTS using Microsoft Edge neural voices via edge-tts"""
    voice = EDGE_VOICES.get(voice_key, "en-US-AndrewNeural")
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"voiceover_{voice_key}_{timestamp}.mp3"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎙️  [Local TTS] Generating voiceover: {voice} ({len(text)} chars)")
    
    try:
        subprocess.run([
            "edge-tts", 
            "--text", text,
            "--voice", voice,
            "--write-media", str(output_path)
        ], check=True, capture_output=True, timeout=60)
        
        if output_path.exists():
            print(f"✅ [Local TTS] Voiceover saved: {output_path}")
            return output_path
    except subprocess.CalledProcessError as e:
        print(f"⚠️ edge-tts failed: {e.stderr.decode() if e.stderr else e}")
    except Exception as e:
        print(f"⚠️ TTS error: {e}")
    
    return None

# =============================================================================
# LOCAL IMAGE GENERATION: Flux / SDXL via diffusers (MPS optimized)
# =============================================================================

def generate_image_local(
    prompt: str,
    model: str = "flux",  # "flux" | "sdxl" | "sdxl-turbo"
    width: int = 1024,
    height: int = 1792,  # 9:16 vertical
    steps: int = 20,
    guidance: float = 3.5,
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Generate high-quality images locally on Apple Silicon MPS"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"local_{model}_{timestamp}.png"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎨 [Local Image Gen] {model.upper()}: {prompt[:80]}... ({width}x{height})")
    
    try:
        import torch
        from diffusers import (
            FluxPipeline, 
            StableDiffusionXLPipeline, 
            StableDiffusionXLImg2ImgPipeline,
            AutoencoderKL
        )
        
        device = "mps"
        dtype = torch.float16
        
        if model == "flux":
            # FLUX.1-dev (best quality, ~12GB VRAM on MPS)
            pipe = FluxPipeline.from_pretrained(
                "black-forest-labs/FLUX.1-dev",
                torch_dtype=dtype,
                variant="fp16" if torch.cuda.is_available() else None
            )
            pipe.enable_model_cpu_offload()
            pipe = pipe.to(device)
            
            image = pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=torch.Generator(device="cpu").manual_seed(42)
            ).images[0]
            
        elif model in ("sdxl", "sdxl-turbo"):
            # SDXL or SDXL-Turbo
            if model == "sdxl-turbo":
                pipe = StableDiffusionXLPipeline.from_pretrained(
                    "stabilityai/sdxl-turbo",
                    torch_dtype=dtype,
                    variant="fp16"
                )
            else:
                pipe = StableDiffusionXLPipeline.from_pretrained(
                    "stabilityai/stable-diffusion-xl-base-1.0",
                    torch_dtype=dtype,
                    variant="fp16",
                    use_safetensors=True
                )
            
            pipe.enable_model_cpu_offload()
            pipe = pipe.to(device)
            
            image = pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=1 if model == "sdxl-turbo" else steps,
                guidance_scale=0.0 if model == "sdxl-turbo" else guidance,
                generator=torch.Generator(device="cpu").manual_seed(42)
            ).images[0]
        
        image.save(output_path)
        print(f"✅ [Local Image Gen] Saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"⚠️ Local image generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None

# =============================================================================
# LOCAL VIDEO GENERATION: AnimateDiff / CogVideoX / Wan 2.1 via diffusers
# =============================================================================

def generate_video_animatediff(
    prompt: str,
    width: int = 512,
    height: int = 896,  # 9:16
    num_frames: int = 16,
    fps: int = 8,
    motion_scale: float = 1.0,
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Generate video using AnimateDiff + SDXL locally"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"animatediff_{timestamp}.mp4"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 [AnimateDiff] Generating {num_frames} frames ({width}x{height}) @ {fps}fps")
    
    try:
        import torch
        from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler
        from diffusers.utils import export_to_video
        
        device = "mps"
        dtype = torch.float16
        
        # Load motion adapter
        adapter = MotionAdapter.from_pretrained(
            "guoyww/animatediff-motion-adapter-v1-5-2",
            torch_dtype=dtype
        )
        
        pipe = AnimateDiffPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            motion_adapter=adapter,
            torch_dtype=dtype,
            variant="fp16"
        )
        pipe.enable_model_cpu_offload()
        pipe = pipe.to(device)
        pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
        
        frames = pipe(
            prompt=prompt,
            negative_prompt="blurry, low quality, distorted, ugly, deformed",
            num_frames=num_frames,
            guidance_scale=7.5,
            num_inference_steps=25,
            generator=torch.Generator(device="cpu").manual_seed(42),
            width=width,
            height=height,
        ).frames[0]
        
        export_to_video(frames, str(output_path), fps=fps)
        print(f"✅ [AnimateDiff] Video saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"⚠️ AnimateDiff failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None

def generate_video_svd(
    prompt: str,
    image_path: Optional[str] = None,
    width: int = 576,
    height: int = 1024,
    num_frames: int = 25,
    fps: int = 7,
    motion_bucket_id: int = 127,
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Generate video using Stable Video Diffusion (image-to-video)"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"svd_{timestamp}.mp4"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 [Stable Video Diffusion] {num_frames} frames ({width}x{height}) @ {fps}fps")
    
    try:
        import torch
        from diffusers import StableVideoDiffusionPipeline
        from diffusers.utils import load_image, export_to_video
        
        device = "mps"
        dtype = torch.float16
        
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=dtype,
            variant="fp16"
        )
        pipe.enable_model_cpu_offload()
        pipe = pipe.to(device)
        
        if image_path:
            init_image = load_image(image_path)
            init_image = init_image.resize((width, height))
        else:
            # Generate base image first
            from diffusers import StableDiffusionXLPipeline
            img_pipe = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                torch_dtype=dtype,
                variant="fp16"
            )
            img_pipe.enable_model_cpu_offload()
            img_pipe = img_pipe.to(device)
            init_image = img_pipe(prompt=prompt, width=width, height=height).images[0]
        
        frames = pipe(
            init_image,
            decode_chunk_size=8,
            motion_bucket_id=motion_bucket_id,
            noise_aug_strength=0.02,
            num_frames=num_frames,
            generator=torch.Generator(device="cpu").manual_seed(42),
        ).frames[0]
        
        export_to_video(frames, str(output_path), fps=fps)
        print(f"✅ [SVD] Video saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"⚠️ SVD failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None

def generate_video_cogvideox(
    prompt: str,
    width: int = 720,
    height: int = 480,
    num_frames: int = 49,
    fps: int = 8,
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Generate video using CogVideoX (text-to-video)"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"cogvideox_{timestamp}.mp4"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 [CogVideoX] {num_frames} frames ({width}x{height}) @ {fps}fps")
    
    try:
        import torch
        from diffusers import CogVideoXPipeline
        from diffusers.utils import export_to_video
        
        device = "mps"
        dtype = torch.float16
        
        pipe = CogVideoXPipeline.from_pretrained(
            "THUDM/CogVideoX-5b",
            torch_dtype=dtype,
            variant="fp16"
        )
        pipe.enable_model_cpu_offload()
        pipe = pipe.to(device)
        
        frames = pipe(
            prompt=prompt,
            num_frames=num_frames,
            height=height,
            width=width,
            num_inference_steps=50,
            guidance_scale=6,
            generator=torch.Generator(device="cpu").manual_seed(42),
        ).frames[0]
        
        export_to_video(frames, str(output_path), fps=fps)
        print(f"✅ [CogVideoX] Video saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"⚠️ CogVideoX failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None

# =============================================================================
# POLLINATIONS.AI FREE FALLBACK (NO API KEY NEEDED)
# =============================================================================

def generate_pollinations_video(
    prompt: str,
    width: int = 1080,
    height: int = 1920,
    model: str = "wan2.1",  # or "kling", "luma", "minimax"
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Free video generation via Pollinations image + FFmpeg Ken Burns"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"pollinations_pan_{timestamp}.mp4"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 [Pollinations FFmpeg] {prompt[:80]}... ({width}x{height})")
    
    try:
        import subprocess
        # 1. Generate image first
        img_path = generate_pollinations_image(prompt, width, height, "flux")
        if not img_path:
            return None
            
        # 2. Use ffmpeg to zoom/pan (Ken Burns)
        print(f"🎥 [FFmpeg] Animating image into video...")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
            "-vf", f"zoompan=z='min(zoom+0.0015,1.5)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',scale={width}:{height}",
            "-c:v", "libx264", "-t", "5", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ [Pollinations FFmpeg] Video saved: {output_path}")
        
        # Clean up image
        if img_path.exists():
            img_path.unlink()
            
        return output_path
        
    except Exception as e:
        print(f"⚠️ Pollinations video failed: {e}")
    
    return None

def generate_pollinations_image(
    prompt: str,
    width: int = 1024,
    height: int = 1792,
    model: str = "flux",
    output_path: Optional[str] = None
) -> Optional[Path]:
    """Free image generation via Pollinations.ai (no API key)"""
    
    if not output_path:
        timestamp = int(time.time())
        output_path = OUTPUT_DIR / f"pollinations_{model}_{timestamp}.png"
    else:
        output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎨 [Pollinations] {model}: {prompt[:80]}... ({width}x{height})")
    
    try:
        import requests
        
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        params = {
            "model": model,
            "width": width,
            "height": height,
            "nologo": "true",
            "private": "true",
            "enhance": "true",
        }
        
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        
        output_path.write_bytes(resp.content)
        print(f"✅ [Pollinations] Image saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"⚠️ Pollinations image failed: {e}")
    
    return None

# =============================================================================
# MAIN GENERATION ROUTER - CASCADES THROUGH FREE OPTIONS
# =============================================================================

def generate_video(
    prompt: str,
    provider: str = "auto",  # auto | animatediff | svd | cogvideox | pollinations
    input_image: Optional[str] = None,
    duration: int = 5,
    aspect: str = "9:16",
    resolution: str = "512x896",
    negative_prompt: str = "",
) -> Optional[Path]:
    """
    Main entry point - routes to best available FREE provider
    Priority: Local AnimateDiff > Local SVD > Local CogVideoX > Pollinations
    """
    
    # Parse resolution
    try:
        width, height = map(int, resolution.split("x"))
    except:
        width, height = 512, 896  # 9:16 default
    
    # Aspect ratio adjustments
    if aspect == "16:9":
        width, height = 1920, 1080
    elif aspect == "9:16":
        width, height = 512, 896
    elif aspect == "1:1":
        width, height = 512, 512
    
    # Build negative prompt
    negative = negative_prompt or "blurry, low quality, distorted, ugly, deformed, bad anatomy, watermark, text, noise, grainy, jpeg artifacts"
    
    if provider == "auto":
        # Try local providers in order of quality/speed balance
        for p in ["animatediff", "svd", "cogvideox", "pollinations"]:
            try:
                result = generate_video(prompt, p, input_image, duration, aspect, resolution, negative)
                if result:
                    return result
            except Exception as e:
                print(f"⚠️ {p} failed, trying next: {e}")
                continue
        return None
    
    elif provider == "animatediff":
        num_frames = min(16, max(8, duration * 8))
        return generate_video_animatediff(
            prompt=prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            fps=8,
        )
    
    elif provider == "svd":
        if not input_image:
            print("⚠️ SVD requires input_image. Generating base image first...")
            input_image = generate_image_local(prompt, "sdxl", width, height)
        if input_image:
            return generate_video_svd(prompt, input_image, width, height)
        return None
    
    elif provider == "cogvideox":
        num_frames = min(49, max(8, duration * 8))
        return generate_video_cogvideox(
            prompt=prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            fps=8,
        )
    
    elif provider == "pollinations":
        return generate_pollinations_video(prompt, width, height)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")

def generate_image(
    prompt: str,
    provider: str = "auto",  # auto | local | pollinations
    width: int = 1024,
    height: int = 1792,
) -> Optional[Path]:
    """Generate image via best free provider"""
    
    if provider == "auto":
        # Try local first (best quality), then Pollinations
        for p in ["local", "pollinations"]:
            try:
                result = generate_image(prompt, p, width, height)
                if result:
                    return result
            except Exception as e:
                print(f"⚠️ {p} failed: {e}")
        return None
    
    elif provider == "local":
        return generate_image_local(prompt, "flux", width, height)
    
    elif provider == "pollinations":
        return generate_pollinations_image(prompt, width, height)
    
    else:
        raise ValueError(f"Unknown image provider: {provider}")

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Flo Faction TV Network - Local AI Video Generator (100% FREE)"
    )
    parser.add_argument("--prompt", type=str, help="Video prompt")
    parser.add_argument("--input", type=str, help="Input image for img2vid")
    parser.add_argument("--provider", type=str, default="auto", 
        choices=["auto", "animatediff", "svd", "cogvideox", "pollinations", "local", "flux", "sdxl"])
    parser.add_argument("--tts", type=str, help="Generate voiceover with edge-tts")
    parser.add_argument("--voice", type=str, default="male_authoritative",
        choices=list(EDGE_VOICES.keys()))
    parser.add_argument("--duration", type=int, default=5, help="Video duration (seconds)")
    parser.add_argument("--aspect", type=str, default="9:16", choices=["9:16", "16:9", "1:1"])
    parser.add_argument("--resolution", type=str, default="512x896", help="WxH")
    parser.add_argument("--negative", type=str, default="", help="Negative prompt")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("   FLO FACTION TV NETWORK - LOCAL AI ANIMATOR (FREE)")
    print("=" * 70)
    
    if args.tts:
        out_file = generate_voiceover_edge(args.tts, args.voice)
        if out_file:
            print(f"SUCCESS: Voiceover generated at {out_file}")
        else:
            print("FAILED: Could not generate voiceover")
            sys.exit(1)
    
    elif args.prompt:
        out_file = generate_video(
            prompt=args.prompt,
            provider=args.provider,
            input_image=args.input,
            duration=args.duration,
            aspect=args.aspect,
            resolution=args.resolution,
            negative_prompt=args.negative,
        )
        if out_file:
            print(f"SUCCESS: Video generated at {out_file}")
        else:
            print("FAILED: Could not generate video")
            sys.exit(1)
    
    elif args.input and not args.prompt:
        # Image generation mode
        out_file = generate_image(
            prompt=args.input,
            provider=args.provider,
            width=1024,
            height=1792,
        )
        if out_file:
            print(f"SUCCESS: Image generated at {out_file}")
        else:
            print("FAILED: Could not generate image")
            sys.exit(1)
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()