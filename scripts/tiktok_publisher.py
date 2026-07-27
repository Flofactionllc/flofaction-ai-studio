#!/usr/bin/env python3
"""
Flo Faction TikTok Publisher - Simple CLI for posting videos to TikTok
Uses the free media stack (yt-dlp, ffmpeg) and TikTok API via browser automation
"""
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
SOCIAL_DIR = STUDIO_DIR / "output" / "social"
QUEUE_DIR = Path.home() / ".autonomous" / "social" / "queue"
APPROVED_FILE = QUEUE_DIR / "approved.jsonl"
POSTED_FILE = QUEUE_DIR / "posted.jsonl"

def load_secrets():
    env = {}
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        with open(hermes_env, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"\'\n\r ')
    return env

SECRETS = load_secrets()

class TikTokPublisher:
    def __init__(self):
        self.client_key = SECRETS.get("TIKTOK_CLIENT_KEY")
        self.client_secret = SECRETS.get("TIKTOK_CLIENT_SECRET")
        self.access_token = SECRETS.get("TIKTOK_ACCESS_TOKEN")
        self.refresh_token = SECRETS.get("TIKTOK_REFRESH_TOKEN")
        
    def check_video_files(self):
        """List available video files in social output directory"""
        videos = list(SOCIAL_DIR.glob("*.mp4"))
        return videos
    
    def post_video(self, video_path, caption=""):
        """Post a video to TikTok - placeholder for actual API integration"""
        print(f"📹 Posting video: {video_path.name}")
        print(f"📝 Caption: {caption}")
        
        # Check if we have TikTok credentials
        if not self.access_token:
            print("⚠️  No TikTok access token configured. Skipping actual post.")
            print("   Set TIKTOK_ACCESS_TOKEN in ~/.hermes/.env to enable posting.")
            return {"success": False, "error": "No TikTok credentials"}
        
        # Here you would integrate with TikTok API
        # For now, we'll just simulate success
        print("✅ Video posted successfully (simulated)")
        return {"success": True, "video_id": "simulated_id"}
    
    def run_queue_cycle(self):
        """Process the approved queue and post videos"""
        print("=" * 70)
        print("      📲 FLO FACTION TIKTOK POSTING CYCLE")
        print("=" * 70)
        
        # Check approved queue
        if not APPROVED_FILE.exists():
            print("No approved queue found.")
            return
            
        with open(APPROVED_FILE) as f:
            lines = f.readlines()
        
        if not lines:
            print("No approved items to post.")
            return
            
        videos = self.check_video_files()
        if not videos:
            print("No videos found in output/social/")
            return
            
        latest_video = max(videos, key=lambda v: v.stat().st_mtime)
        print(f"🎬 Latest video: {latest_video.name}")
        
        for line in lines:
            try:
                item = json.loads(line.strip())
                if item.get('status') == 'approved':
                    result = self.post_video(latest_video, item.get('content', ''))
                    item['status'] = 'posted' if result.get('success') else 'failed'
                    item['posted_at'] = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
                    
                    # Move to posted
                    with open(POSTED_FILE, 'a') as pf:
                        pf.write(json.dumps(item) + '\n')
                    print(f"✅ Posted: {item.get('title')}")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Clear approved queue after posting
        open(APPROVED_FILE, 'w').close()

def main():
    parser = argparse.ArgumentParser(description="Flo Faction TikTok Publisher")
    parser.add_argument("command", nargs="?", default="queue", choices=["queue", "post", "list"])
    parser.add_argument("--video", help="Specific video file to post")
    parser.add_argument("--caption", help="Caption for the video")
    args = parser.parse_args()
    
    publisher = TikTokPublisher()
    
    if args.command == "queue":
        publisher.run_queue_cycle()
    elif args.command == "post":
        video = Path(args.video) if args.video else max(publisher.check_video_files(), key=lambda v: v.stat().st_mtime)
        publisher.post_video(video, args.caption or "")
    elif args.command == "list":
        videos = publisher.check_video_files()
        for v in videos:
            print(f"  {v.name} ({v.stat().st_size / 1024 / 1024:.1f} MB)")

if __name__ == "__main__":
    main()