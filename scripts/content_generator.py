#!/usr/bin/env python3
"""
=============================================================================
FLO FACTION TV NETWORK - MASTER CONTENT & REEL GENERATOR
=============================================================================
Supports Multi-Division Content Categories with explicit integration of 
Flo Faction services and products, tailored specifically for platforms: 
TikTok, YouTube Shorts, and IG Reels.
=============================================================================
"""
import os
import sys
import json
import time
from pathlib import Path

STUDIO_DIR = Path("/Users/pauledwards/flofaction-ai-studio")
SCRIPTS_DIR = STUDIO_DIR / "daily-content"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

DIVISIONS = {
    "wealth_insurance": {
        "topics": [
            "How an IUL locks in market gains with zero downside risk",
            "Tax-free wealth strategy vs traditional 401k traps",
            "Protecting your family's future with Flo Faction Insurance",
            "How smart wealth strategist Paul Edwards structures tax-free growth"
        ],
        "products": "Flo Faction Insurance (IULs, Annuities, Wealth Strategy)",
        "cta": "Link in bio to get your free Flo Faction Insurance quote today."
    },
    "phone_arbitrage": {
        "topics": [
            "How Flo Faction Arbitrage generates daily cashflow buying used phones",
            "Scoring phones against Gemstar pricebook for maximum profit",
            "Turning local trade-ins into instant cleared PayPal deposits",
            "Step-by-step phone buyback arbitrage breakdown"
        ],
        "products": "Flo Faction Arbitrage (Gemstar Buyback Program)",
        "cta": "DM us 'ARBITRAGE' to learn how to flip phones for daily cashflow."
    },
    "ai_automation": {
        "topics": [
            "How 15 autonomous AI agents run Flo Faction 24/7",
            "Eliminating manual work with OpenClaw & Hermes workflows",
            "Why autonomous agent fleets beat standard SaaS tools",
            "Inside the Flo Faction self-healing architecture"
        ],
        "products": "Flo Faction AI Automation Consulting & OpenClaw",
        "cta": "Want to automate your business? Visit flofaction.com for a free consultation."
    },
    "flofaction_tv": {
        "topics": [
            "Flo Faction TV: Premiering tonight's masterclass episode",
            "Inside Flo Faction Network: Good Credit Isn't A Plan (Full Breakdown)",
            "Building an unstoppable multi-channel media ecosystem",
            "Flo Faction TV Network Showcase & Special Feature"
        ],
        "products": "Flo Faction TV Network Exclusives",
        "cta": "Subscribe to Flo Faction TV Network on YouTube for full episodes!"
    },
    "comedy_variety": {
        "topics": [
            "When the AI agent passes your job interview and takes your seat",
            "Office banter: Pretending to be CEO when the automated system emails your boss",
            "When your smart fridge starts negotiating crypto trades at 3 AM",
            "Tech vs Reality: Trying to automate your life and causing chaos",
            "Family dinner debate: Explaining autonomous income to your relatives"
        ],
        "products": "Flo Faction TV Comedy Skits",
        "cta": "Follow Flo Faction TV Network for daily animated comedy and relatable skits!"
    }
}

PLATFORMS = ["tiktok", "youtube_shorts", "ig_reels"]

def generate_multi_division_40_reels():
    today = time.strftime("%Y-%m-%d")
    out_file = SCRIPTS_DIR / f"{today}-master-40-reels.json"

    categories = list(DIVISIONS.keys())
    reels = []

    for i in range(1, 41):
        cat = categories[(i - 1) % len(categories)]
        div_data = DIVISIONS[cat]
        topics = div_data["topics"]
        topic = topics[((i - 1) // len(categories)) % len(topics)]
        platform = PLATFORMS[i % len(PLATFORMS)]
        
        # Platform tailoring
        if platform == "tiktok":
            format_spec = "9:16 vertical reel, fast-paced hook, trending audio"
            hashtags = ["#FloFactionTV", f"#{cat.replace('_', '')}", "#fyp", "#trending"]
        elif platform == "youtube_shorts":
            format_spec = "9:16 vertical short, educational value, bold captions"
            hashtags = ["#FloFactionTV", f"#{cat.replace('_', '')}", "#Shorts", "#Business"]
        else: # ig_reels
            format_spec = "9:16 vertical reel, high aesthetic, clean typography"
            hashtags = ["#FloFactionTV", f"#{cat.replace('_', '')}", "#Explore", "#WealthStrategy"]

        reels.append({
            "slot": i,
            "division": cat,
            "platform": platform,
            "title": f"Flo Faction TV #{i} [{cat.upper()}]: {topic}",
            "topic": topic,
            "featured_product": div_data["products"],
            "format": format_spec,
            "cta": div_data["cta"],
            "hashtags": hashtags
        })

    data = {
        "date": today,
        "target_rate": "40 reels/day per account",
        "brand_identity": "Flo Faction TV Network",
        "divisions_included": categories,
        "reels": reels
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Generated 40 Multi-Division Reels (Platform Tailored) for Flo Faction TV Network: {out_file}")
    return out_file

if __name__ == "__main__":
    generate_multi_division_40_reels()