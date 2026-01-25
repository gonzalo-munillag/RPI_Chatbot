# =============================================================================
# Telegram Bridge for Prometheus AI
# =============================================================================
# 
# This Dockerfile builds the Telegram bot that connects to Ollama AI.
# It's a lightweight Python container that runs the telegram bot.
#
# Build:
#   docker buildx build --platform linux/arm64,linux/amd64 \
#       -t your-username/telegram-bridge:latest \
#       -f telegram-bridge/Dockerfile --push .
#
# =============================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY telegram-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY telegram-bridge/bot.py .

# Environment variables (set these in docker-compose.yml)
# TELEGRAM_BOT_TOKEN - Required: Your bot token from @BotFather
# AUTHORIZED_USERS   - Required: Comma-separated Telegram user IDs
# OLLAMA_URL         - Optional: Ollama API URL (default: http://ollama:8000)
# TTS_URL            - Optional: Piper TTS URL (default: http://piper-tts:5000)

# Health check - verify the bot process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "python.*bot.py" || exit 1

# Run the bot
CMD ["python", "-u", "bot.py"]

