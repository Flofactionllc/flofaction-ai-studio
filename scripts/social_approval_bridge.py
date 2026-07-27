#!/usr/bin/env python3
"""
===============================================================================
FLO FACTION TV NETWORK - SOCIAL MEDIA APPROVAL BRIDGE
===============================================================================
Sends approval requests to Telegram, iMessage, and WhatsApp with:
- Full video preview (when reel is being posted)
- Editable caption/message
- Direct approval/rejection/edit via reply
- Routes response back to approval queue
===============================================================================
"""

import os
import sys
import json
import time
import asyncio
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment
def load_keys():
    keys = {}
    for path in [
        Path.home() / ".hermes" / ".env",
        Path.home() / ".flofaction-secrets.env",
        Path.home() / ".autonomous" / ".env",
        Path("/Users/pauledwards/flofaction-ai-studio/.env"),
    ]:
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        keys[k.strip()] = v.strip('"\' \n\r')
    return keys

KEYS = load_keys()

# Telegram config
TELEGRAM_BOT_TOKEN = KEYS.get("TELEGRAM_BOT_TOKEN") or "8760478007:***"
TELEGRAM_CHAT_ID = KEYS.get("TELEGRAM_CHAT_ID") or "8466073022"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# iMessage config (uses existing bridge)
IMESSAGE_TARGETS = [
    "paulisluap@icloud.com",
    "jordan23.paul@gmail.com", 
    "flofactionllc@gmail.com",
]

# Approval queue paths
SOCIAL_DIR = Path.home() / ".autonomous" / "social" / "approved"
DRAFTS_FILE = SOCIAL_DIR / "drafts.jsonl"
APPROVED_FILE = SOCIAL_DIR / "approved.jsonl"
POSTED_FILE = SOCIAL_DIR / "posted.jsonl"
PENDING_APPROVALS_FILE = SOCIAL_DIR / "pending_approvals.jsonl"

for f in [DRAFTS_FILE, APPROVED_FILE, POSTED_FILE, PENDING_APPROVALS_FILE]:
    if not f.exists():
        f.write_text("")

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SocialPost:
    id: str
    platform: str
    title: str
    content: str
    media_path: Optional[str]
    media_type: str  # "video" | "image" | "text"
    status: str = "pending_approval"  # pending_approval | approved | rejected | posted | failed
    created_at: str = ""
    approved_at: Optional[str] = None
    posted_at: Optional[str] = None
    edited_content: Optional[str] = None
    approval_channel: Optional[str] = None  # "telegram" | "imessage" | "whatsapp"
    approval_message_id: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"

# ============================================================================
# TELEGRAM INTEGRATION
# ============================================================================

async def send_telegram_approval(post: SocialPost) -> Optional[Dict]:
    """Send approval request to Telegram with video preview and inline buttons"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare message
            caption = f"""
🎬 <b>SOCIAL POST APPROVAL REQUEST</b>

<b>Platform:</b> {post.platform.upper()}
<b>Title:</b> {post.title}
<b>ID:</b> <code>{post.id}</code>

<b>Content:</b>
{post.content[:1000]}{'...' if len(post.content) > 1000 else ''}

<b>Media:</b> {post.media_type.upper()} - {os.path.basename(post.media_path) if post.media_path else 'None'}
            """.strip()
            
            # Create inline keyboard for approval actions
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ APPROVE", "callback_data": f"approve:{post.id}"},
                        {"text": "❌ REJECT", "callback_data": f"reject:{post.id}"}
                    ],
                    [
                        {"text": "✏️ EDIT CONTENT", "callback_data": f"edit:{post.id}"},
                        {"text": "👁️ PREVIEW VIDEO", "callback_data": f"preview:{post.id}"}
                    ]
                ]
            }
            
            # Send video if available
            if post.media_path and post.media_type == "video" and Path(post.media_path).exists():
                file_size = Path(post.media_path).stat().st_size
                if file_size < 50_000_000:  # Telegram limit 50MB
                    with open(post.media_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('chat_id', TELEGRAM_CHAT_ID)
                        data.add_field('caption', caption)
                        data.add_field('parse_mode', 'HTML')
                        data.add_field('reply_markup', json.dumps(keyboard))
                        data.add_field('video', f, filename=os.path.basename(post.media_path), content_type='video/mp4')
                        
                        async with session.post(f"{TELEGRAM_API}/sendVideo", data=data) as resp:
                            result = await resp.json()
                            if result.get("ok"):
                                msg_id = result["result"]["message_id"]
                                return {"message_id": msg_id, "channel": "telegram"}
                else:
                    # File too large, send as document or just message
                    pass
            
            # Send message with image or just text
            if post.media_path and post.media_type == "image" and Path(post.media_path).exists():
                with open(post.media_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', TELEGRAM_CHAT_ID)
                    data.add_field('caption', caption)
                    data.add_field('parse_mode', 'HTML')
                    data.add_field('reply_markup', json.dumps(keyboard))
                    data.add_field('photo', f, filename=os.path.basename(post.media_path), content_type='image/jpeg')
                    
                    async with session.post(f"{TELEGRAM_API}/sendPhoto", data=data) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            msg_id = result["result"]["message_id"]
                            return {"message_id": msg_id, "channel": "telegram"}
            else:
                # Send text message with buttons
                data = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": caption,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(keyboard)
                }
                async with session.post(f"{TELEGRAM_API}/sendMessage", json=data) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        msg_id = result["result"]["message_id"]
                        return {"message_id": msg_id, "channel": "telegram"}
    
    except Exception as e:
        print(f"⚠️ Telegram send failed: {e}")
    
    return None

async def handle_telegram_callback(callback_data: str, chat_id: str, message_id: int, from_user: str):
    """Handle Telegram inline button callbacks"""
    action, post_id = callback_data.split(":", 1)
    
    # Load pending approval
    post = load_pending_approval(post_id)
    if not post:
        await telegram_edit_message(chat_id, message_id, "❌ Approval request not found or expired")
        return
    
    if action == "approve":
        post.status = "approved"
        post.approved_at = datetime.utcnow().isoformat() + "Z"
        post.approval_channel = "telegram"
        save_pending_approval(post)
        move_to_approved(post)
        
        await telegram_edit_message(
            chat_id, message_id,
            f"✅ <b>APPROVED</b> by {from_user}\n\n"
            f"Platform: {post.platform}\n"
            f"Title: {post.title}\n\n"
            f"Post has been queued for publishing."
        )
        
    elif action == "reject":
        post.status = "rejected"
        save_pending_approval(post)
        
        await telegram_edit_message(
            chat_id, message_id,
            f"❌ <b>REJECTED</b> by {from_user}\n\n"
            f"Platform: {post.platform}\n"
            f"Title: {post.title}"
        )
        
    elif action == "edit":
        # Ask for new content
        await telegram_send_message(
            chat_id,
            f"✏️ <b>EDIT MODE</b> for post {post_id}\n\n"
            f"Reply to this message with the NEW content you want to post.\n"
            f"Current content:\n{post.content[:500]}"
        )
        # Store that we're in edit mode for this user/post
        # This would need a more complex state machine
        
    elif action == "preview":
        # Re-send video if available
        if post.media_path and Path(post.media_path).exists():
            # Already sent above, just confirm
            await telegram_edit_message(
                chat_id, message_id,
                f"📹 Video preview already sent above.\n\n"
                f"File: {os.path.basename(post.media_path)}"
            )

async def telegram_edit_message(chat_id: str, message_id: int, text: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/editMessageText", json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        })

async def telegram_send_message(chat_id: str, text: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })

# ============================================================================
# IMESSAGE INTEGRATION (via existing bridge)
# ============================================================================

def send_imessage_approval(post: SocialPost) -> bool:
    """Send approval request via iMessage bridge"""
    try:
        # Use the existing iMessage bridge
        message = f"""🎬 SOCIAL POST APPROVAL REQUEST

Platform: {post.platform.upper()}
Title: {post.title}
ID: {post.id}

Content:
{post.content[:500]}{'...' if len(post.content) > 500 else ''}

Media: {post.media_type.upper()} - {os.path.basename(post.media_path) if post.media_path else 'None'}

REPLY WITH:
✅ APPROVE {post.id}  - to approve and queue for posting
❌ REJECT {post.id}  - to reject
✏️ EDIT {post.id} <new content>  - to edit and approve
👁️ PREVIEW {post.id}  - to view video preview
"""
        
        # Send via AppleScript to all targets
        success_count = 0
        for target in IMESSAGE_TARGETS:
            script = (
                'tell application "Messages"\n'
                f'    set targetService to 1st service whose service type = iMessage\n'
                f'    set targetBuddy to buddy "{target}" of targetService\n'
                f'    send "{message.replace(chr(34), chr(92)+chr(34)).replace(chr(10), chr(92)+"n")}" to targetBuddy\n'
                'end tell'
            )
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                success_count += 1
        
        return success_count > 0
        
    except Exception as e:
        print(f"⚠️ iMessage send failed: {e}")
        return False

# ============================================================================
# WHATSAPP INTEGRATION (placeholder - needs WhatsApp Business API)
# ============================================================================

def send_whatsapp_approval(post: SocialPost) -> bool:
    """Send approval request via WhatsApp (requires WhatsApp Business API)"""
    # This would require WhatsApp Business API setup
    # For now, we can use a webhook or Twilio integration
    print(f"⚠️ WhatsApp integration not yet configured. Skipping.")
    return False

# ============================================================================
# APPROVAL QUEUE MANAGEMENT
# ============================================================================

def load_pending_approval(post_id: str) -> Optional[SocialPost]:
    """Load a pending approval from file"""
    if not PENDING_APPROVALS_FILE.exists():
        return None
    
    with open(PENDING_APPROVALS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("id") == post_id:
                    return SocialPost(**data)
            except:
                continue
    return None

def save_pending_approval(post: SocialPost):
    """Save/update a pending approval"""
    # Read all, update or add
    posts = []
    if PENDING_APPROVALS_FILE.exists():
        with open(PENDING_APPROVALS_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if data.get("id") != post.id:
                            posts.append(data)
                    except:
                        pass
    
    posts.append(asdict(post))
    
    with open(PENDING_APPROVALS_FILE, 'w') as f:
        for p in posts:
            f.write(json.dumps(p) + '\n')

def move_to_approved(post: SocialPost):
    """Move approved post to approved queue"""
    post.status = "approved"
    post.approved_at = datetime.utcnow().isoformat() + "Z"
    
    with open(APPROVED_FILE, 'a') as f:
        f.write(json.dumps(asdict(post)) + '\n')
    
    # Remove from pending
    save_pending_approval(post)  # This will update status

def create_approval_request(post: SocialPost) -> SocialPost:
    """Create a new approval request and send to all channels"""
    post.status = "pending_approval"
    save_pending_approval(post)
    
    # Send to all channels
    print(f"📤 Sending approval request for {post.id} to all channels...")
    
    # Telegram (async)
    try:
        import asyncio
        result = asyncio.run(send_telegram_approval(post))
        if result:
            post.approval_message_id = result.get("message_id")
            post.approval_channel = "telegram"
            save_pending_approval(post)
            print(f"✅ Telegram: Sent (message_id: {result.get('message_id')})")
    except Exception as e:
        print(f"⚠️ Telegram: {e}")
    
    # iMessage
    try:
        if send_imessage_approval(post):
            post.approval_channel = (post.approval_channel or "") + ",imessage"
            save_pending_approval(post)
            print(f"✅ iMessage: Sent")
    except Exception as e:
        print(f"⚠️ iMessage: {e}")
    
    # WhatsApp
    try:
        if send_whatsapp_approval(post):
            post.approval_channel = (post.approval_channel or "") + ",whatsapp"
            save_pending_approval(post)
            print(f"✅ WhatsApp: Sent")
    except Exception as e:
        print(f"⚠️ WhatsApp: {e}")
    
    return post

# ============================================================================
# INTEGRATION WITH SOCIAL APPROVAL QUEUE
# ============================================================================

def process_social_queue():
    """Process the social approval queue and send pending items for approval"""
    # Load drafts from social-approval-queue.py
    drafts = []
    if DRAFTS_FILE.exists():
        with open(DRAFTS_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        drafts.append(json.loads(line))
                    except:
                        pass
    
    print(f"📋 Found {len(drafts)} drafts in queue")
    
    for draft in drafts:
        # Check if already in pending approvals
        existing = load_pending_approval(draft.get("id", ""))
        if existing:
            print(f"   ⏭️  {draft.get('id')} already pending approval")
            continue
        
        # Create SocialPost from draft
        post = SocialPost(
            id=draft.get("id", ""),
            platform=draft.get("platform", "unknown"),
            title=draft.get("title", "Untitled"),
            content=draft.get("content", ""),
            media_path=draft.get("media_path"),
            media_type=draft.get("meta", {}).get("is_media", False) and "video" or "text",
        )
        
        # Send for approval
        create_approval_request(post)
        print(f"   ✅ Sent for approval: {post.id}")

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Flo Faction Social Media Approval Bridge")
    parser.add_argument("--process-queue", action="store_true", help="Process all drafts and send for approval")
    parser.add_argument("--send-approval", type=str, help="Send specific post ID for approval")
    parser.add_argument("--list-pending", action="store_true", help="List all pending approvals")
    parser.add_argument("--test-telegram", action="store_true", help="Test Telegram connection")
    parser.add_argument("--test-imessage", action="store_true", help="Test iMessage connection")
    
    args = parser.parse_args()
    
    if args.process_queue:
        process_social_queue()
    
    elif args.send_approval:
        post = load_pending_approval(args.send_approval)
        if not post:
            # Try to load from drafts
            if DRAFTS_FILE.exists():
                with open(DRAFTS_FILE) as f:
                    for line in f:
                        data = json.loads(line.strip())
                        if data.get("id") == args.send_approval:
                            post = SocialPost(
                                id=data.get("id", ""),
                                platform=data.get("platform", "unknown"),
                                title=data.get("title", "Untitled"),
                                content=data.get("content", ""),
                                media_path=data.get("media_path"),
                                media_type=data.get("meta", {}).get("is_media", False) and "video" or "text",
                            )
                            break
        if post:
            create_approval_request(post)
        else:
            print(f"❌ Post not found: {args.send_approval}")
    
    elif args.list_pending:
        if PENDING_APPROVALS_FILE.exists():
            with open(PENDING_APPROVALS_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            print(f"  {data['id']} | {data['platform']} | {data['status']} | {data['title'][:50]}")
                        except:
                            pass
        else:
            print("No pending approvals")
    
    elif args.test_telegram:
        import asyncio
        result = asyncio.run(telegram_send_message(TELEGRAM_CHAT_ID, "🤖 Test message from Flo Faction approval bridge"))
        print("Telegram test:", "OK" if result else "FAILED")
    
    elif args.test_imessage:
        send_imessage_approval(SocialPost(
            id="test", platform="test", title="Test", content="Test message", media_path=None, media_type="text"
        ))
        print("iMessage test sent")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()