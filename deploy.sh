#!/usr/bin/env bash
# =============================================================================
# FLO FACTION AI STUDIO AUTOMATED DEPLOYMENT & PRODUCTION HARNESS
# Hybrid Architecture: HyperFrames Cinematic + Free API Matrix
# =============================================================================
set -e

STUDIO_DIR="/Users/pauledwards/flofaction-ai-studio"
cd "$STUDIO_DIR"

TODAY=$(date +%Y-%m-%d)

echo "========================================================================="
echo "  🚀 FLO FACTION AI STUDIO HYBRID PRODUCTION CYCLE ($TODAY)"
echo "========================================================================="

echo "🌐 Step 1: Starting Local Free LLM Gateway (Background Router)..."
python3 scripts/free_llm_gateway.py &
GATEWAY_PID=$!
sleep 3

echo "📝 Step 2: Generating daily scripts..."
python3 scripts/content_generator.py --date "$TODAY"

echo "🎬 Step 3: Producing 100% Free AI Video Assets (Wan 2.1 / Veo 2 / Pollinations)..."
python3 scripts/cloud_ai_animator.py \
  --prompt "Cinematic 4K shot of an AI technology laboratory with glowing blue holographic displays" \
  --aspect "9:16"

echo "🎤 Step 4: Synthesizing Free Studio Voiceover (Edge-TTS / Kokoro)..."
python3 scripts/cloud_ai_animator.py \
  --tts "Welcome to Flo Faction TV Network. The premiere zero-cost autonomous AI studio."

echo "🎞️ Step 5: HyperFrames Cinematic Assembly..."
python3 videography/engines/cinematic_engine.py --prompt "Cinematic 4K shot of Flo Faction autonomous logistics and AI studio" --preset "studio_commercial"

echo "📲 Step 6: Pushing assets to Percy Miller Facebook, TikTok, YouTube Shorts, and IG..."
python3 scripts/social_poster.py --cycle

# Cleanup background gateway
kill $GATEWAY_PID || true

echo "========================================================================="
echo "✨ FLO FACTION HYBRID DAILY PRODUCTION CYCLE COMPLETE FOR $TODAY!"
echo "========================================================================="