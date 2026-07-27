# =============================================================================
# FLO FACTION AI STUDIO & AUTONOMOUS AGENT FLEET - 24/7 FREE CLOUD CONTAINER
# Deploys to Oracle Free Tier, Render.com, Koyeb, or Fly.io (100% FREE TIER)
# =============================================================================
FROM python:3.11-slim

# Install system dependencies (FFmpeg, Node.js, Git, Curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    sqlite3 \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir requests edge-tts aiohttp aiofiles python-dotenv

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV FREE_GATEWAY="http://127.0.0.1:8088/v1"

# Expose port for cloud webhooks
EXPOSE 8080

# Start script
CMD ["python3", "scripts/hitl_messenger.py", "--caption", "Cloud Fleet Online", "--title", "24/7 Cloud Bot"]
