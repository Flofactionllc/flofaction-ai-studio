#!/usr/bin/env python3
"""
================================================================================
FLO FACTION TV NETWORK - HITL DAEMON (PERSISTENT)
================================================================================
Persistent Human-in-the-Loop approval daemon that runs continuously.
Receives approval requests from social poster, sends to Telegram/iMessage,
polls for replies, and writes approved content back to social queue.

Integrates with existing iMessage bridge and social approval queue.
================================================================================
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
import aiohttp
import aiofiles

# =============================================================================
# CONFIGURATION
# =============================================================================

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

# Telegram
TELEGRAM_BOT_TOKEN = KEYS.get("TELEGRAM_BOT_TOKEN", "8760478007:***")
TELEGRAM_CHAT_ID = KEYS.get("TELEGRAM_CHAT_ID", "8466073022")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# iMessage
IMESSAGE_TARGETS = [
    "paulisluap@icloud.com",
    "jordan23.paul@gmail.com",
    "flofactionllc@gmail.com",
]

# Paths
HITL_DIR = Path.home() / ".autonomous" / "hitl"
HITL_DIR.mkdir(parents=True, exist_ok=True)
PENDING_FILE = HITL_DIR / "pending_approvals.jsonl"
PROCESSED_FILE = HITL_DIR / "processed_approvals.jsonl"
SOCIAL_DIR = Path.home() / ".autonomous" / "social" / "approved"
DRAFTS_FILE = SOCIAL_DIR / "drafts.jsonl"
APPROVED_FILE = SOCIAL_DIR / "approved.jsonl"

for f in [PENDING_FILE, PROCESSED_FILE]:
    if not f.exists():
        f.write_text("")

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HitLRequest:
    post_id: str
    platform: str
    title: str
    caption: str
    video_path: Optional[str] = None
    video_size_mb: float = 0.0
    status: str = "pending"  # pending, sent, approved, rejected, edited, timeout
    created_at: str = ""
    sent_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    final_caption: Optional[str] = None
    telegram_message_id: Optional[int] = None
    imessage_sent: bool = False
    reply_text: Optional[str] = None
    reply_channel: Optional[str] = None
    reply_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"

# =============================================================================
# TELEGRAM INTEGRATION
# =============================================================================

async def send_telegram_approval(req: HitLRequest) -> Optional[int]:
    """Send approval request via Telegram with video + inline buttons"""
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
                if file_size <= 50_000_000:  # 50MB limit
                    print(f"📤 Sending video to Telegram ({file_size/1024/1024:.1f} MB)...")
                    
                    data = aiohttp.FormData()
                    data.add_field('chat_id', TELEGRAM_CHAT_ID)
                    data.add_field('caption', caption)
                    data.add_field('parse_mode', 'HTML')
                    data.add_field('reply_markup', json.dumps(keyboard))
                    data.add_field('supports_streaming', 'true')
                    
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


async def telegram_edit_message(chat_id: str, message_id: int, text: str):
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/editMessageText", json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        })


async def telegram_answer_callback(callback_query_id: str, text: str = ""):
    async with aiohttp.ClientSession() as session:
        await session.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_query_id,
            "text": text
        })


async def poll_telegram_replies(last_update_id: int = 0) -> List[Dict]:
    """Poll Telegram for new callback queries and messages"""
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
                                    "action": action,
                                    "channel": "telegram",
                                    "user": from_user,
                                    "chat_id": str(chat_id),
                                    "message_id": msg_id,
                                    "callback_query_id": cb["id"],
                                    "timestamp": datetime.utcnow().isoformat() + "Z"
                                })
                        
                        elif "message" in update and "text" in update["message"]:
                            msg = update["message"]
                            text = msg["text"]
                            chat_id = msg["chat"]["id"]
                            from_user = msg["from"]["username"] or msg["from"]["first_name"]
                            
                            # Check if replying to our approval message
                            if msg.get("reply_to_message"):
                                replied = msg["reply_to_message"]
                                caption_or_text = replied.get("caption") or replied.get("text") or ""
                                if "Post ID:" in caption_or_text:
                                    import re
                                    match = re.search(r"Post ID:\s*<code>([^<]+)</code>", caption_or_text)
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


# =============================================================================
# IMESSAGE INTEGRATION
# =============================================================================

def send_imessage_approval(req: HitLRequest) -> bool:
    """Send approval request via iMessage to all targets"""
    success_count = 0
    
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
                
                text_lower = text.lower()
                action = None
                reply_text = None
                
                if f"approve {post_id}" in text_lower or f"approve {post_id}" in text_lower:
                    action = "approve"
                elif f"reject {post_id}" in text_lower:
                    action = "reject"
                elif f"edit {post_id}" in text_lower:
                    action = "edit"
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


# =============================================================================
# HITL REQUEST MANAGEMENT
# =============================================================================

def load_pending() -> Dict[str, HitLRequest]:
    pending = {}
    if not PENDING_FILE.exists():
        return pending
    
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
    
    req.sent_at = datetime.utcnow().isoformat() + "Z"
    req.status = "sent"
    
    # Save updated request
    pending = load_pending()
    pending[req.post_id] = req
    save_pending(pending)
    
    print(f"✅ Approval request sent to {sum([req.telegram_message_id is not None, req.imessage_sent])} channels")


def handle_reply(req: HitLRequest, reply: Dict) -> Optional[str]:
    """Process a reply and update request, return final caption if approved"""
    
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
        
        # Send confirmation to Telegram
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
        req.status = "pending"  # Stay pending
        return None
    
    # Save updated request
    pending = load_pending()
    pending[req.post_id] = req
    save_pending(pending)
    
    return req.final_caption


# =============================================================================
# MAIN DAEMON LOOP
# =============================================================================

async def run_daemon(poll_interval: int = 5):
    """Main daemon loop - processes pending approvals and polls for replies"""
    
    print("=" * 60)
    print("  HITL DAEMON STARTED")
    print("=" * 60)
    print(f"Polling interval: {poll_interval}s")
    print(f"Pending file: {PENDING_FILE}")
    print(f"Telegram: {'✓' if TELEGRAM_BOT_TOKEN != '***' else '✗'}")
    print(f"iMessage: ✓")
    print()
    
    last_telegram_update = 0
    imessage_since = time.time()
    
    # Process any existing pending approvals on startup
    pending = load_pending()
    for req in pending.values():
        if req.status == "pending":
            print(f"📋 Found existing pending: {req.post_id}")
            await send_all_channels(req)
        elif req.status == "sent":
            print(f"📋 Resuming sent request: {req.post_id}")
    
    print("✅ Daemon ready - waiting for approvals and replies...")
    print()
    
    while True:
        try:
            # 1. Check for new approval requests from social queue
            # (Social poster will create requests via CLI or we can poll drafts)
            
            # 2. Poll Telegram for replies
            try:
                telegram_replies = await poll_telegram_replies(last_telegram_update)
                for reply in telegram_replies:
                    if reply["post_id"] in pending:
                        final = handle_reply(pending[reply["post_id"]], reply)
                        if final:
                            print(f"\n🎉 FINAL APPROVED CAPTION for {reply['post_id']}:")
                            print(final)
                            print()
            except:
                pass
            
            # 3. Poll iMessage for replies
            try:
                for req in list(pending.values()):
                    if req.status == "sent":
                        imessage_replies = poll_imessage_replies(req.post_id, imessage_since)
                        for reply in imessage_replies:
                            if reply["post_id"] in pending:
                                handle_reply(pending[reply["post_id"]], reply)
                imessage_since = time.time()
            except:
                pass
            
            # 4. Check for completed approvals and move to social queue
            completed = []
            for post_id, req in pending.items():
                if req.status in ("approved", "edited") and req.final_caption:
                    # Move to social approval queue
                    approved_entry = {
                        "id": req.post_id,
                        "title": req.title,
                        "platform": req.platform,
                        "status": "approved",
                        "created_at": req.created_at,
                        "approved_at": req.approved_at,
                        "posted_at": None,
                        "content": req.final_caption,
                        "media_path": req.video_path,
                        "meta": {
                            "source_file": req.video_path,
                            "is_media": req.video_path is not None
                        }
                    }
                    
                    APPROVED_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(APPROVED_FILE, "a") as f:
                        f.write(json.dumps(approved_entry) + "\n")
                    
                    print(f"✅ Moved to approved queue: {post_id}")
                    completed.append(post_id)
                
                elif req.status == "rejected":
                    print(f"❌ Rejected, removing: {post_id}")
                    completed.append(post_id)
                
                elif req.status == "timeout":
                    print(f"⏰ Timeout, removing: {post_id}")
                    completed.append(post_id)
            
            # Remove completed requests
            for post_id in completed:
                del pending[post_id]
            
            save_pending(pending)
            
            # 5. Small delay
            await asyncio.sleep(poll_interval)
            
        except KeyboardInterrupt:
            print("\n🛑 Daemon stopped by user")
            break
        except Exception as e:
            print(f"⚠️ Daemon error: {e}")
            await asyncio.sleep(poll_interval)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def request_approval_cli(args):
    """CLI to create a new approval request (called by social poster)"""
    post_id = args.post_id or f"post_{int(time.time())}_{os.urandom(4).hex()}"
    
    req = create_approval_request(
        post_id=post_id,
        platform=args.platform,
        title=args.title,
        caption=args.caption,
        video_path=args.video
    )
    
    # Send immediately
    asyncio.run(send_all_channels(req))
    
    print(f"✅ Approval request sent for {post_id}")
    print(f"   Waiting for approval (timeout: {args.timeout}s)...")
    
    # Wait for reply
    final = asyncio.run(poll_for_reply(post_id, args.timeout))
    
    if final:
        print(f"\n🎉 APPROVED!")
        print(f"Final caption: {final}")
        sys.exit(0)
    else:
        print(f"\n❌ No approval received")
        sys.exit(1)


async def poll_for_reply(post_id: str, timeout: int) -> Optional[str]:
    """Poll for a reply on a specific post_id"""
    start = time.time()
    pending = load_pending()
    
    last_telegram = 0
    imessage_since = time.time()
    
    while time.time() - start < timeout:
        # Check if approved
        if post_id in pending:
            req = pending[post_id]
            if req.status in ("approved", "edited") and req.final_caption:
                return req.final_caption
            elif req.status == "rejected":
                return None
        
        # Poll Telegram
        try:
            replies = await poll_telegram_replies(last_telegram)
            for reply in replies:
                if reply["post_id"] == post_id:
                    req = pending.get(post_id)
                    if req:
                        return handle_reply(req, reply)
        except:
            pass
        
        # Poll iMessage
        try:
            imessage_replies = poll_imessage_replies(post_id, imessage_since)
            for reply in imessage_replies:
                req = pending.get(post_id)
                if req:
                    return handle_reply(req, reply)
            imessage_since = time.time()
        except:
            pass
        
        await asyncio.sleep(2)
    
    return None


def check_status_cli(args):
    """Check status of a post"""
    pending = load_pending()
    req = pending.get(args.status)
    if req:
        print(json.dumps(asdict(req), indent=2))
    else:
        print(f"No request found for {args.status}")


def main():
    parser = argparse.ArgumentParser(description="Flo Faction HITL Approval Daemon")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Daemon mode
    daemon_parser = subparsers.add_parser("daemon", help="Run as persistent daemon")
    daemon_parser.add_argument("--interval", type=int, default=5, help="Poll interval (seconds)")
    
    # Request approval (called by social poster)
    req_parser = subparsers.add_parser("request", help="Create and send approval request")
    req_parser.add_argument("--video", type=str, help="Path to video file")
    req_parser.add_argument("--caption", type=str, required=True, help="Draft caption")
    req_parser.add_argument("--title", type=str, default="Flo Faction Post", help="Post title")
    req_parser.add_argument("--platform", type=str, default="tiktok", help="Platform name")
    req_parser.add_argument("--post-id", type=str, help="Unique post ID")
    req_parser.add_argument("--timeout", type=int, default=300, help="Approval timeout (seconds)")
    
    # Check status
    status_parser = subparsers.add_parser("status", help="Check approval status")
    status_parser.add_argument("status", type=str, help="Post ID to check")
    
    # Test Telegram
    subparsers.add_parser("test-telegram", help="Test Telegram connection")
    
    # Test iMessage
    subparsers.add_parser("test-imessage", help="Test iMessage connection")
    
    args = parser.parse_args()
    
    if args.command == "daemon":
        asyncio.run(run_daemon(args.interval))
    elif args.command == "request":
        request_approval_cli(args)
    elif args.command == "status":
        check_status_cli(args)
    elif args.command == "test-telegram":
        asyncio.run(test_telegram())
    elif args.command == "test-imessage":
        send_imessage_approval(HitLRequest(
            id="test", platform="test", title="Test", content="Test", video_path=None
        ))
        print("iMessage test sent")
    else:
        parser.print_help()


async def test_telegram():
    """Test Telegram connection"""
    msg_id = await send_telegram_approval(HitLRequest(
        post_id="test_001",
        platform="test",
        title="Test Post",
        caption="This is a test approval request",
        video_path=None
    ))
    if msg_id:
        print(f"✅ Telegram test successful (msg_id: {msg_id})")
    else:
        print("❌ Telegram test failed")


if __name__ == "__main__":
    import time
    import os
    main()