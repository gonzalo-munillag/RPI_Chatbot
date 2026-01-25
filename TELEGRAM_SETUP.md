# 📱 Telegram Bot Setup Guide

This guide explains how to set up a Telegram bot that connects to your locally-hosted Ollama AI.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Prerequisites](#-prerequisites)
- [Step 1: Create Bot via BotFather](#-step-1-create-bot-via-botfather)
- [Step 2: Get Your User ID](#-step-2-get-your-user-id)
- [Step 3: Configure Environment](#-step-3-configure-environment)
- [Step 4: Deploy](#-step-4-deploy)
- [Step 5: Test](#-step-5-test)
- [Group Chat Setup](#-group-chat-setup)
- [Features](#-features)
- [Troubleshooting](#-troubleshooting)

---

## 🏗️ Overview

### Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────┐    ┌────────┐
│  Telegram   │───▶│  Telegram Bridge │───▶│ FastAPI │───▶│ Ollama │
│   (User)    │◀───│    (Python)      │◀───│  (API)  │◀───│(Gemma) │
└─────────────┘    └──────────────────┘    └─────────┘    └────────┘
                            │
                            ▼
                     ┌────────────┐
                     │ Piper TTS  │───▶ 🔊 Speaker
                     └────────────┘
```

### How It Works

1. **Telegram Bot API** - Your bot polls Telegram's servers for new messages
2. **Telegram Bridge** - Python container receives messages, forwards to Ollama
3. **Ollama** - Generates AI response
4. **Response** - Sent back through Telegram
5. **Optional TTS** - "speak" keyword triggers voice output on the Pi

### Why Telegram over WhatsApp?

| Feature | WhatsApp | Telegram |
|---------|----------|----------|
| API Type | Unofficial (reverse-engineered) | **Official Bot API** ✅ |
| Risk of Ban | High | Very low |
| Rate Limits | Aggressive | Generous (30 msg/sec) |
| Setup Complexity | QR code + session management | Just a token |
| Reliability | Can break with updates | Stable API |

---

## 📋 Prerequisites

- Raspberry Pi with Docker and the Ollama stack running
- Telegram account
- 5 minutes

---

## 🤖 Step 1: Create Bot via BotFather

1. Open Telegram
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow the prompts:
   - **Name**: `Prometheus AI` (display name)
   - **Username**: `prometheus_ai_bot` (must end in `bot`)
5. BotFather replies with your **API Token**:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/prometheus_ai_bot.
   
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. **Save this token!** You'll need it for configuration.

---

## 🔑 Step 2: Get Your User ID

The bot only responds to authorized users. You need your Telegram user ID.

1. Open Telegram
2. Search for `@userinfobot`
3. Send any message (like "hi")
4. It replies with your ID:
   ```
   Id: 123456789
   First: YourName
   ```
5. **Save this ID!**

For multiple users, collect all their IDs (comma-separated in config).

---

## ⚙️ Step 3: Configure Environment

Add to your `.env` file on the Raspberry Pi:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
```

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_AUTHORIZED_USERS` | Comma-separated user IDs who can use the bot |

---

## 🚀 Step 4: Deploy

### Option A: Full rebuild (if building from source)

```bash
# On your build machine
./build-and-push.sh

# On Pi
cd /var/www/ollama_chatbot
sudo docker-compose pull telegram
sudo docker-compose up -d telegram
```

### Option B: Just the Telegram service

```bash
# On Pi
cd /var/www/ollama_chatbot
sudo docker-compose up -d telegram
```

### Verify it's running

```bash
sudo docker ps | grep telegram
# Should show: telegram-bridge ... Up

sudo docker logs telegram-bridge
# Should show: 🤖 Prometheus Telegram Bot Starting
```

---

## ✅ Step 5: Test

1. Open Telegram
2. Search for your bot's username
3. Send `/start`
4. Send `Hello!`
5. You should get an AI response

### Test TTS (if speaker connected)

Send: `speak Hello, can you hear me?`

The Pi should speak the response aloud.

---

## 👥 Group Chat Setup

To use the bot in Telegram groups:

### Step 1: Disable Group Privacy

```
1. Open @BotFather
2. Send /mybots
3. Select your bot
4. Bot Settings → Group Privacy → Turn OFF
```

This allows the bot to see all group messages (not just commands).

### Step 2: Add Bot to Group

1. Open your Telegram group
2. Tap group name → Add Members
3. Search for your bot's username
4. Add it

### Step 3: Trigger the Bot

In groups, the bot only responds when:
- Mentioned: `@your_bot_username what's 2+2?`
- Or message starts with: `Prometheus what's 2+2?`

---

## ✨ Features

| Feature | Usage |
|---------|-------|
| **Direct Chat** | Just send any message |
| **Group Chat** | Start with `Prometheus` or mention `@botname` |
| **Voice Output** | Start message with `speak` |
| **Clear History** | Send `/clear` |
| **Help** | Send `/help` |

### Conversation Memory

The bot remembers the last 10 messages per user for context-aware conversations.

---

## 🔧 Troubleshooting

### "Not authorized" error

Your user ID isn't in `TELEGRAM_AUTHORIZED_USERS`. Add it:

```bash
# On Pi, edit .env
nano /var/www/ollama_chatbot/.env

# Add your ID
TELEGRAM_AUTHORIZED_USERS=123456789

# Restart
sudo docker-compose up -d telegram
```

### Bot not responding

```bash
# Check if container is running
sudo docker ps | grep telegram

# Check logs
sudo docker logs telegram-bridge --tail 50

# Common issues:
# - Invalid token
# - Network issue (can't reach Telegram API)
# - Ollama not running
```

### "speak" not working

Ensure Piper TTS is running:
```bash
sudo docker ps | grep piper
curl http://localhost:5000/health
```

### Bot slow to respond

Ollama may be processing. Check:
```bash
sudo docker logs ollama-gemma --tail 20
```

---

## 📊 docker-compose.yml Reference

```yaml
telegram:
  image: ${DOCKER_USERNAME}/telegram-bridge:latest
  container_name: telegram-bridge
  restart: unless-stopped
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - AUTHORIZED_USERS=${TELEGRAM_AUTHORIZED_USERS}
    - OLLAMA_URL=http://ollama:8000
    - TTS_URL=http://piper-tts:5000
    - MAX_CONTEXT_MESSAGES=10
  depends_on:
    - ollama
    - piper-tts
  networks:
    - chatbot-network
```

---

*This guide is part of the [Prometheus RPI Chatbot](README.md) project.*

