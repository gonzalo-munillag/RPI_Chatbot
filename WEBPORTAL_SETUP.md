# Web Portal Setup Guide

A ChatGPT-style web interface for your Raspberry Pi AI assistant.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [How It Works](#how-it-works)
4. [Files Structure](#files-structure)
5. [Step-by-Step Setup](#step-by-step-setup)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Web Portal provides a browser-based chat interface to interact with your AI assistant. It's an alternative to WhatsApp that you fully control.

### Features

- **ChatGPT-style UI** - Clean, modern, responsive design
- **Password Protection** - Only you can access it
- **"speak" Keyword** - Type "speak" before your message to hear the AI's response through the Pi's speaker
- **Conversation History** - Messages persist during your session
- **Mobile Friendly** - Works on phones and tablets

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR BROWSER                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Web Portal UI (index.html)                             │    │
│  │  - Type messages in chat input                          │    │
│  │  - See AI responses in chat window                      │    │
│  │  - "speak hello" → triggers voice output                │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP Request (POST /chat)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              WEB PORTAL CONTAINER (Port 5054)                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  server.py (FastAPI)                                    │    │
│  │                                                         │    │
│  │  1. Receives your message                               │    │
│  │  2. Checks if "speak" keyword is present                │    │
│  │  3. Sends message to Ollama AI                          │    │
│  │  4. Gets AI response                                    │    │
│  │  5. If "speak": calls Piper TTS                         │    │
│  │  6. Returns response to browser                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   OLLAMA (Port 8000)    │     │  PIPER TTS (Port 5000)  │
│                         │     │                         │
│  - Gemma 2B model       │     │  - Text-to-Speech       │
│  - Generates responses  │     │  - Plays on Pi speaker  │
└─────────────────────────┘     └─────────────────────────┘
```

---

## How It Works

### Normal Message Flow

```
1. You type: "What is the capital of France?"
2. Browser sends POST request to http://pi-ip:5054/chat
3. server.py receives the message
4. server.py calls Ollama API at http://ollama:8000/chat
5. Ollama returns: "The capital of France is Paris."
6. server.py sends response back to browser
7. Browser displays the response in the chat window
```

### "speak" Keyword Flow

```
1. You type: "speak What is the capital of France?"
2. Browser sends POST request to http://pi-ip:5054/chat
3. server.py detects "speak" keyword, removes it from message
4. server.py calls Ollama API with: "What is the capital of France?"
5. Ollama returns: "The capital of France is Paris."
6. server.py calls Piper TTS API at http://piper-tts:5000/speak
7. Piper TTS plays "The capital of France is Paris" on Pi's speaker
8. server.py sends response back to browser (you see AND hear it)
```

---

## Files Structure

```
web-portal/
├── Dockerfile           # Container build instructions
├── requirements.txt     # Python dependencies
├── server.py            # FastAPI backend (main logic)
└── static/
    └── index.html       # Chat UI (HTML + CSS + JavaScript)
```

### File Purposes

| File | Purpose |
|------|---------|
| `Dockerfile` | Tells Docker how to build the container |
| `requirements.txt` | Lists Python packages needed |
| `server.py` | The brain - handles requests, talks to Ollama and Piper |
| `static/index.html` | The face - what you see in the browser |

---

## Step-by-Step Setup

### Step 1: Create the Files

All files are created in the `web-portal/` directory of your project.

### Step 2: Build the Docker Image

```bash
# From your development machine
cd /path/to/RPI_Chatbot
./build-and-push.sh
```

### Step 3: Deploy to Raspberry Pi

```bash
# On the Raspberry Pi
cd /var/www/ollama_chatbot
sudo docker-compose pull
sudo docker-compose up -d web-portal
```

### Step 4: Access the Portal

Open your browser and go to:
```
http://<PI_IP_ADDRESS>:5054
```

### Step 5: Login

Enter the password you configured (default: `prometheus`)

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORTAL_PASSWORD` | Login password | `prometheus` |
| `OLLAMA_URL` | Ollama API endpoint | `http://ollama:8000` |
| `TTS_URL` | Piper TTS endpoint | `http://piper-tts:5000` |
| `SESSION_SECRET` | Secret for session tokens | (random) |

### Changing the Password

Edit your `.env` file on the Pi:

```bash
# /var/www/ollama_chatbot/.env
PORTAL_PASSWORD=your_secure_password
```

Then restart:
```bash
sudo docker-compose restart web-portal
```

---

## Usage

### Basic Chat

1. Open the portal in your browser
2. Type your message in the input box
3. Press Enter or click Send
4. See the AI's response appear

### Voice Output (speak)

1. Start your message with `speak`
2. Example: `speak Tell me a joke`
3. The AI will respond in text AND speak through the Pi's speaker

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Send message |
| Shift+Enter | New line (without sending) |

---

## Troubleshooting

### Portal won't load

```bash
# Check if container is running
sudo docker ps | grep web-portal

# Check logs
sudo docker logs web-portal --tail 50
```

### "Connection refused" error

```bash
# Check if Ollama is running
curl http://localhost:8000/health

# Check if all services are up
sudo docker-compose ps
```

### Voice not working

```bash
# Test Piper TTS directly
curl -X POST http://localhost:5000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

### Forgot password

Edit `.env` file and restart the container:
```bash
sudo nano /var/www/ollama_chatbot/.env
# Change PORTAL_PASSWORD=newpassword
sudo docker-compose restart web-portal
```

---

## Security Notes

1. **Change the default password** before exposing to the internet
2. **Use HTTPS** if accessing from outside your home network
3. **Firewall** - Only open port 5054 if you need remote access
4. The portal is bound to `0.0.0.0` by default (accessible from any device on your network)

---

## Next Steps

After setup, you can:

1. Customize the UI colors in `static/index.html`
2. Add more features to `server.py`
3. Set up a reverse proxy (nginx) for HTTPS


