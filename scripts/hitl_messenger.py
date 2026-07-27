#!/usr/bin/env python3
"""
===============================================================================
FLO FACTION TV NETWORK - HUMAN-IN-THE-LOOP MESSENGER (HITL)
===============================================================================
Interactive approval layer for social media posts.
Sends full video + caption to Telegram, iMessage, and WhatsApp.
Halts pipeline and waits for your reply to approve/edit/reject.

Integration:
- Telegram: Uses existing bot token + chat ID (100% free)
- iMessage: Uses macOS AppleScript + local chat.db polling (100% free)
- WhatsApp: Placeholder for Twilio/WhatsApp Business API or unofficial wrapper

Usage:
    python3 hitl_messenger.py --video /path/to/video.mp4 --caption "Draft caption" --platforms tiktok,facebook
    python3 hitl_messenger.py --poll-replies --post-id ABC123
===============================================================================
"""

import os
import sys
import json
import time
import asyncio
import sqlite3
import subprocess
import argparse
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime

# ============================================================================
# CONFIGURATION - Load from environment
# ============================================================================

def load_env():
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

KEYS = load_env()

# Telegram config (from existing env)
TELEGRAM_BOT_TOKEN = KEYS.get("TELEGRAM_BOT_TOKEN", "8760478007:***")
TELEGRAM_CHAT_ID = KEYS.get("TELEGRAM_CHAT_ID", "8466073022")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# iMessage config
IMESSAGE_TARGETS = [
    "paulisluap@icloud.com",
    "jordan23.paul@gmail.com", 
    "flofactionllc@gmail.com",
]

# WhatsApp config (placeholder for Twilio or unofficial wrapper)
WHATSAPP_ENABLED = False
WHATSAPP_ACCOUNT_SID = KEYS.get("TWILIO_ACCOUNT_SID")
WHATSAPP_AUTH_TOKEN = KEYS.get("TWILIO_AUTH_TOKEN")
WHATSAPP_FROM_NUMBER = KEYS.get("TWILIO_WHATSAPP_FROM")
WHATSAPP_TO_NUMBERS = KEYS.get("WHATSAPP_TO_NUMBERS", "").split(",") if KEYS.get("WHATSAPP_TO_NUMBERS") else []

# Storage
HITL_DIR = Path.home() / ".autonomous" / "hitl"
HITL_DIR.mkdir(parents=True, exist_ok=True)
PENDING_FILE = HITL_DIR / "pending_approvals.json"
REPLIES_FILE = HITL_DIR / "hitl_replies.json"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class HitLRequest:
    """A Human-in-the-Loop approval request"""
    post_id: str
    platform: str
    title: str
    caption: str
    video_path: Optional[str]
    video_size_mb: float = 0.0
    status: str = "pending"  # pending, approved, rejected, edited, timeout
    created_at: str = ""
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    final_caption: Optional[str] = None
    telegram_message_id: Optional[int] = None
    imessage_sent: bool = False
    whatsapp_sent: bool = False
    reply_text: Optional[str] = None
    reply_channel: Optional[str] = None
    reply_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"

# ============================================================================
# TELEGRAM INTEGRATION
# ============================================================================

async def send_telegram_approval(req: HitLRequest) -> Optional[int]:
    """Send approval request via Telegram with video + inline buttons"""
    import aiohttp
    import aiofiles
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "***":
        print("⚠️ Telegram token not configured")
        return None
    
    caption = f"""🎬 <b>SOCIAL POST APPROVAL REQUIRED</b>

<b>Platform:</b> {req.platform.upper()}
<b>Title:</b> {req.title}
<b>Post ID:</b> <code>{req.post_id}</code>

<b>Caption:</b>
{req.caption[:800]}{'...' if len(req.caption) > 800 else ''}

<b>Video:</b> {f'{req.video_size_mb:.1f} MB' if req.video_path else 'None'}
"""
    
    # Inline keyboard for quick actions
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ APPROVE", "callback_data": f"hitl_approve:{req.post_id}"},
                {"text": "❌ REJECT", "callback_data": f"hitl_reject:{req.post_id}"}
            ],
            [
                {"text": "✏️ EDIT & APPROVE", "callback_data": f"hitl_edit:{req.post_id}"},
                {"text": "👁️ PREVIEW", "callback_data": f"hitl_preview:{req.post_id}"}
            ]
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            if req.video_path and Path(req.video_path).exists():
                file_size = Path(req.video_path).stat().st_size
                if file_size <= 50_000_000:  # 50MB Telegram limit
                    print(f"📤 Sending video to Telegram ({file_size/1024/1024:.1f} MB)...")
                    
                    data = aiohttp.FormData()
                    data.add_field('chat_id', TELEGRAM_CHAT_ID)
                    data.add_field('caption', caption)
                    data.add_field('parse_mode', 'HTML')
                    data.add_field('supports_streaming', 'true')
                    data.add_field('reply_markup', json.dumps(keyboard))
                    
                    async with aiofiles.open(req.video_path, 'rb') as f:
                        file_content = await f.read()
                        data.add_field('video', file_content, 
                                      filename=Path(req.video_path).name,
                                      content_type='video/mp4')
                    
                    async with session.post(f"{TELEGRAM_API}/sendVideo", data=data) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            msg_id = result["result"]["message_id"]
                            print(f"✅ Telegram video sent (msg_id: {msg_id})")
                            return msg_id
                        else:
                            print(f"⚠️ Telegram video send failed: {result}")
                else:
                    print(f"⚠️ Video too large for Telegram ({file_size/1024/1024:.1f} MB > 50 MB)")
            
            # Fallback: send message without video
            async with session.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard)
            }) as resp:
                result = await resp.json()
                if result.get("ok"):
                    msg_id = result["result"]["message_id"]
                    print(f"✅ Telegram message sent (msg_id: {msg_id})")
                    return msg_id
                else:
                    print(f"⚠️ Telegram send failed: {result}")
                    
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")
    
    return None


async def poll_telegram_replies(last_update_id: int = 0) -> List[Dict]:
    """Poll Telegram for new messages/callbacks"""
    import aiohttp
    
    replies = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{TELEGRAM_API}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 10,
                "allowed_updates": ["message", "callback_query"]
            }) as resp:
                result = await resp.json()
                
                if result.get("ok"):
                    for update in result["result"]:
                        update_id = update["update_id"]
                        
                        if "callback_query" in update:
                            # Inline button press
                            cb = update["callback_query"]
                            data = cb["data"]
                            chat_id = cb["message"]["chat"]["id"]
                            msg_id = cb["message"]["message_id"]
                            from_user = cb["from"]["username"] or cb["from"]["first_name"]
                            
                            if data.startswith("hitl_"):
                                action, post_id = data.split(":", 1)
                                action = action.replace("hitl_", "")
                                replies.append({
                                    "post_id": post_id,
                                    "action": action,  # approve, reject, edit, preview
                                    "channel": "telegram",
                                    "user": from_user,
                                    "chat_id": str(chat_id),
                                    "message_id": msg_id,
                                    "timestamp": datetime.utcnow().isoformat() + "Z"
                                })
                        
                        elif "message" in update and "text" in update["message"]:
                            # Direct text reply (for edit mode)
                            msg = update["message"]
                            text = msg["text"]
                            chat_id = msg["chat"]["id"]
                            from_user = msg["from"]["username"] or msg["from"]["first_name"]
                            
                            # Check if this is a reply to our approval message
                            if msg.get("reply_to_message"):
                                replied_msg = msg["reply_to_message"]
                                if "Post ID:" in (replied_msg.get("caption") or replied_msg.get("text") or ""):
                                    # Extract post ID
                                    import re
                                    match = re.search(r"Post ID:\s*<code>([^<]+)</code>", 
                                                     replied_msg.get("caption") or replied_msg.get("text") or "")
                                    if match:
                                        post_id = match.group(1)
                                        replies.append({
                                            "post_id": post_id,
                                            "action": "edit",
                                            "channel": "telegram",
                                            "user": from_user,
                                            "text": text,
                                            "chat_id": str(chat_id),
                                            "message_id": msg["message_id"],
                                            "timestamp": datetime.utcnow().isoformat() + "Z"
                                        })
                        
                        last_update_id = max(last_update_id, update_id)
    
    except Exception as e:
        print(f"⚠️ Telegram poll error: {e}")
    
    return replies


async def telegram_edit_message(chat_id: str, message_id: int, text: str):
    """Edit a sent Telegram message"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/editMessageText", json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        })


async def telegram_answer_callback(callback_query_id: str, text: str = ""):
    """Answer a callback query"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_query_id,
            "text": text
        })

# ============================================================================
# IMESSAGE INTEGRATION
# ============================================================================

def send_imessage_approval(req: HitLRequest) -> bool:
    """Send approval request via iMessage to all targets"""
    success_count = 0
    
    # Build message
    msg = f"""🎬 SOCIAL POST APPROVAL REQUIRED

Platform: {req.platform.upper()}
Title: {req.title}
Post ID: {req.post_id}

Caption:
{req.caption[:800]}{'...' if len(req.caption) > 800 else ''}

Video: {f'{req.video_size_mb:.1f} MB' if req.video_path else 'None'}

━━━━━━━━━━━━━━━━
REPLY WITH ONE OF:
✅ APPROVE {req.post_id}
❌ REJECT {req.post_id}
✏️ EDIT {req.post_id} [new caption text]
👁️ PREVIEW {req.post_id}
"""
    
    for target in IMESSAGE_TARGETS:
        script = (
            'tell application "Messages"\n'
            f'    set targetService to 1st service whose service type = iMessage\n'
            f'    set targetBuddy to buddy "{target}" of targetService\n'
            f'    send "{msg.replace(chr(34), chr(92)+chr(34)).replace(chr(10), chr(92)+"n")}" to targetBuddy\n'
            'end tell'
        )
        try:
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                success_count += 1
                print(f"✅ iMessage sent to {target}")
            else:
                print(f"⚠️ iMessage failed to {target}: {result.stderr}")
        except Exception as e:
            print(f"⚠️ iMessage error for {target}: {e}")
    
    return success_count > 0


def poll_imessage_replies(post_id: str, since_time: float) -> List[Dict]:
    """Poll local iMessage chat.db for replies"""
    replies = []
    
    try:
        # Use node:sqlite via existing bridge approach
        # For simplicity, use sqlite3 CLI
        db_path = str(Path.home() / "Library" / "Messages" / "chat.db")
        
        query = f"""
        SELECT message.ROWID as rid, handle.id as sender, message.text, message.date
        FROM message 
        JOIN handle ON message.handle_id = handle.ROWID
        WHERE message.is_from_me = 0 
        AND message.text IS NOT NULL
        AND (message.text LIKE '%{post_id}%')
        AND message.date > {int(since_time * 1_000_000_000)}
        ORDER BY message.date ASC LIMIT 20;
        """
        
        result = subprocess.run(
            ['sqlite3', '-json', db_path, query],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            rows = json.loads(result.stdout)
            for row in rows:
                text = row.get("text", "").strip()
                sender = row.get("sender", "")
                
                if not text or not sender:
                    continue
                
                # Parse action
                text_lower = text.lower()
                action = None
                reply_text = None
                
                if f"approve {post_id}" in text_lower or f"approve {post_id}" in text_lower:
                    action = "approve"
                elif f"reject {post_id}" in text_lower:
                    action = "reject"
                elif f"edit {post_id}" in text_lower:
                    action = "edit"
                    # Extract new caption after "edit POST_ID"
                    import re
                    match = re.search(rf'edit\s+{re.escape(post_id)}\s+(.+)', text, re.IGNORECASE)
                    if match:
                        reply_text = match.group(1).strip()
                elif f"preview {post_id}" in text_lower:
                    action = "preview"
                
                if action:
                    replies.append({
                        "post_id": post_id,
                        "action": action,
                        "channel": "imessage",
                        "user": sender,
                        "text": reply_text,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
    
    except Exception as e:
        print(f"⚠️ iMessage poll error: {e}")
    
    return replies

# ============================================================================
# WHATSAPP INTEGRATION (Placeholder)
# ============================================================================

def send_whatsapp_approval(req: HitLRequest) -> bool:
    """Send approval via WhatsApp (requires Twilio or unofficial wrapper)"""
    if not WHATSAPP_ENABLED:
        print("⚠️ WhatsApp not configured (set TWILIO credentials to enable)")
        return False
    
    # Would integrate with Twilio WhatsApp API or whatsapp-web.js
    # For now, placeholder
    print("⚠️ WhatsApp integration not yet implemented")
    return False

def poll_whatsapp_replies(post_id: str) -> List[Dict]:
    """Poll WhatsApp for replies"""
    return []

# ============================================================================
# CORE HITL LOGIC
# ============================================================================

def load_pending() -> Dict[str, HitLRequest]:
    """Load all pending approval requests"""
    if not PENDING_FILE.exists():
        return {}
    
    pending = {}
    try:
        with open(PENDING_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    req = HitLRequest(**data)
                    pending[req.post_id] = req
    except Exception as e:
        print(f"⚠️ Load pending error: {e}")
    
    return pending


def save_pending(pending: Dict[str, HitLRequest]):
    """Save all pending requests"""
    try:
        with open(PENDING_FILE, "w") as f:
            for req in pending.values():
                f.write(json.dumps(asdict(req)) + "\n")
    except Exception as e:
        print(f"⚠️ Save pending error: {e}")


def create_approval_request(
    post_id: str,
    platform: str,
    title: str,
    caption: str,
    video_path: Optional[str] = None
) -> HitLRequest:
    """Create a new HITL approval request"""
    
    req = HitLRequest(
        post_id=post_id,
        platform=platform,
        title=title,
        caption=caption,
        video_path=video_path,
        video_size_mb=Path(video_path).stat().st_size / 1024 / 1024 if video_path and Path(video_path).exists() else 0
    )
    
    pending = load_pending()
    pending[post_id] = req
    save_pending(pending)
    
    print(f"📋 Created approval request: {post_id} for {platform}")
    return req


async def send_all_channels(req: HitLRequest):
    """Send approval request to all configured channels"""
    
    # Send to Telegram
    print("📱 Sending to Telegram...")
    msg_id = await send_telegram_approval(req)
    if msg_id:
        req.telegram_message_id = msg_id
    
    # Send to iMessage
    print("📱 Sending to iMessage...")
    req.imessage_sent = send_imessage_approval(req)
    
    # Send to WhatsApp (if enabled)
    if WHATSAPP_ENABLED:
        print("📱 Sending to WhatsApp...")
        req.whatsapp_sent = send_whatsapp_approval(req)
    
    # Save updated request
    pending = load_pending()
    pending[req.post_id] = req
    save_pending(pending)
    
    print(f"✅ Approval request sent to {sum([req.telegram_message_id is not None, req.imessage_sent, req.whatsapp_sent])} channels")


async def poll_all_channels(req: HitLRequest, timeout_sec: int = 300) -> Optional[str]:
    """Poll all channels for a reply, return final caption or None if timeout"""
    
    start_time = time.time()
    last_telegram_update = 0
    imessage_since = time.time()
    
    print(f"⏳ Waiting for approval (timeout: {timeout_sec}s)...")
    print("   Reply via Telegram (buttons), iMessage (text), or WhatsApp")
    
    while time.time() - start_time < timeout_sec:
        # Poll Telegram
        try:
            telegram_replies = await poll_telegram_replies(last_telegram_update)
            for reply in telegram_replies:
                if reply["post_id"] == req.post_id:
                    return handle_reply(req, reply)
        except:
            pass
        
        # Poll iMessage
        try:
            imessage_replies = poll_imessage_replies(req.post_id, imessage_since)
            for reply in imessage_replies:
                if reply["post_id"] == req.post_id:
                    return handle_reply(req, reply)
            imessage_since = time.time()
        except:
            pass
        
        # Poll WhatsApp (if enabled)
        if WHATSAPP_ENABLED:
            try:
                whatsapp_replies = poll_whatsapp_replies(req.post_id)
                for reply in whatsapp_replies:
                    if reply["post_id"] == req.post_id:
                        return handle_reply(req, reply)
            except:
                pass
        
        # Small delay
        await asyncio.sleep(2)
        
        # Progress indicator
        elapsed = int(time.time() - start_time)
        if elapsed % 30 == 0 and elapsed > 0:
            print(f"   ... still waiting ({elapsed}s elapsed)")
    
    print("⏰ Approval timeout - no response received")
    req.status = "timeout"
    pending = load_pending()
    pending[req.post_id] = req
    save_pending(pending)
    return None


def handle_reply(req: HitLRequest, reply: Dict) -> str:
    """Process a reply and update request, return final caption"""
    
    action = reply.get("action", "")
    channel = reply.get("channel", "unknown")
    user = reply.get("user", "unknown")
    text = reply.get("text", "")
    
    print(f"📨 Received {action} from {user} via {channel}")
    
    req.status = action
    req.approved_by = user
    req.approved_at = datetime.utcnow().isoformat() + "Z"
    req.reply_channel = channel
    req.reply_at = datetime.utcnow().isoformat() + "Z"
    
    if action == "approve":
        req.final_caption = req.caption
        req.status = "approved"
        print(f"✅ APPROVED by {user} via {channel}")
        
        # Send confirmation
        if channel == "telegram" and req.telegram_message_id:
            asyncio.create_task(telegram_edit_message(
                TELEGRAM_CHAT_ID, req.telegram_message_id,
                f"✅ <b>APPROVED</b> by @{user}\n\nPosting: {req.title}"
            ))
    
    elif action == "reject":
        req.final_caption = None
        req.status = "rejected"
        print(f"❌ REJECTED by {user} via {channel}")
        
        if channel == "telegram" and req.telegram_message_id:
            asyncio.create_task(telegram_edit_message(
                TELEGRAM_CHAT_ID, req.telegram_message_id,
                f"❌ <b>REJECTED</b> by @{user}"
            ))
    
    elif action == "edit":
        req.final_caption = text
        req.status = "edited"
        print(f"✏️ EDITED by {user} via {channel}: {text[:100]}")
        
        if channel == "telegram" and req.telegram_message_id:
            asyncio.create_task(telegram_edit_message(
                TELEGRAM_CHAT_ID, req.telegram_message_id,
                f"✏️ <b>EDITED & APPROVED</b> by @{user}\n\nNew caption: {text[:200]}"
            ))
    
    elif action == "preview":
        print(f"👁️ PREVIEW requested by {user} via {channel}")
        # Video already sent, just acknowledge
        if channel == "telegram":
            asyncio.create_task(telegram_answer_callback(
                reply.get("callback_query_id", ""), 
                "Video preview sent above!"
            ))
        req.status = "pending"  # Stay pending
        return None  # Don't return final caption
    
    # Save updated request
    pending = load_pending()
    pending[req.post_id] = req
    save_pending(pending)
    
    return req.final_caption


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def run_approval_workflow(
    post_id: str,
    platform: str,
    title: str,
    caption: str,
    video_path: Optional[str] = None,
    timeout: int = 86400
) -> Optional[str]:
    """Complete HITL approval workflow"""
    
    print("=" * 60)
    print("  HITL SOCIAL POST APPROVAL WORKFLOW")
    print("=" * 60)
    print(f"Post ID: {post_id}")
    print(f"Platform: {platform}")
    print(f"Title: {title}")
    print(f"Video: {video_path or 'None'}")
    print()
    
    # Create request
    req = create_approval_request(post_id, platform, title, caption, video_path)
    
    # Send to all channels
    await send_all_channels(req)
    
    # Wait for reply
    final_caption = await poll_all_channels(req, timeout)
    
    if final_caption:
        print("\n" + "=" * 60)
        print(f"✅ FINAL APPROVED CAPTION:")
        print(final_caption)
        print("=" * 60)
        return final_caption
    else:
        print("\n❌ No approval received - post not published")
        return None


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Flo Faction HITL Social Post Approval Messenger"
    )
    parser.add_argument("--video", type=str, help="Path to video file")
    parser.add_argument("--caption", type=str, help="Draft caption text")
    parser.add_argument("--title", type=str, default="Flo Faction Post", help="Post title")
    parser.add_argument("--platform", type=str, default="tiktok", help="Platform name")
    parser.add_argument("--post-id", type=str, help="Unique post ID")
    parser.add_argument("--timeout", type=int, default=86400, help="Approval timeout (seconds, default 24h)")
    parser.add_argument("--poll", action="store_true", help="Poll for replies on existing request")
    parser.add_argument("--status", type=str, help="Check status of post ID")
    
    args = parser.parse_args()
    
    if args.status:
        # Check status
        pending = load_pending()
        req = pending.get(args.status)
        if req:
            print(json.dumps(asdict(req), indent=2))
        else:
            print(f"No request found for {args.status}")
        return
    
    if args.poll:
        # Poll for replies
        if not args.post_id:
            print("Error: --post-id required with --poll")
            return
        
        pending = load_pending()
        req = pending.get(args.post_id)
        if not req:
            print(f"No pending request for {args.post_id}")
            return
        
        final = await poll_all_channels(req, timeout=args.timeout)
        if final:
            print(f"APPROVED: {final}")
        else:
            print("No reply received")
        return
    
    # New approval workflow
    post_id = args.post_id or f"post_{int(time.time())}_{os.urandom(4).hex()}"
    
    if not args.caption:
        print("Error: --caption required")
        return
    
    final_caption = await run_approval_workflow(
        post_id=post_id,
        platform=args.platform,
        title=args.title,
        caption=args.caption,
        video_path=args.video,
        timeout=args.timeout
    )
    
    if final_caption:
        print(f"\n🎉 Ready to post with caption:\n{final_caption}")
        sys.exit(0)
    else:
        print("\n❌ Approval not received")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())