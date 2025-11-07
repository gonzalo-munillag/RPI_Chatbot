# 🤖 Ollama Gemma-2-2b Chatbot for Raspberry Pi 5

A dockerized chatbot running Google's Gemma-2-2b model on Raspberry Pi 5, with FastAPI wrapper and WhatsApp integration.

## 📋 Overview

This project provides a complete setup for running a local AI chatbot on Raspberry Pi 5 with:
- **Ollama** - Runs the Gemma-2-2b LLM
- **FastAPI** - REST API wrapper for easy integration
- **Docker** - Containerized for easy deployment
- **WhatsApp Integration** - Chat with your AI via WhatsApp (no public exposure needed!)

## 🏗️ Architecture

```
You → WhatsApp → WhatsApp Bridge (Port 3000) → FastAPI (Port 8000) → Ollama (Port 11434) → Gemma-2-2b
                  (Node.js)                       (Python)              (LLM Engine)
```

**Everything runs locally on your Pi - no public exposure needed!**

## 🚀 Quick Start

### Prerequisites

**On Mac M1 (Build Machine):**
- Docker Desktop with buildx enabled
- Docker Hub account (logged in: `docker login`)
- Git

**On Raspberry Pi 5:**
- Raspberry Pi OS (64-bit)
- Docker installed
- Docker Compose installed
- 8GB RAM (minimum 4GB)
- Watchtower running (for auto-updates)

---

## 📦 Deployment Workflow

### Step 1: Build on Mac M1

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd RPI_Chatbot
   ```

2. **Edit files with your Docker Hub username**
   
   Edit build script:
   ```bash
   nano build-and-push.sh
   ```
   Replace `gonzalomg0` on line 10 with YOUR Docker Hub username.
   
   Edit docker-compose:
   ```bash
   nano docker-compose.yml
   ```
   Replace `gonzalomg0` on line 9 with YOUR Docker Hub username.

3. **Build and push to Docker Hub**
   ```bash
   ./build-and-push.sh
   ```
   
   This will:
   - Build for ARM64 (Raspberry Pi) and AMD64 (Mac)
   - Push to Docker Hub
   - Take 10-15 minutes on first build

---

### Step 2: One-Time Setup on Raspberry Pi

1. **SSH into your Raspberry Pi**
   ```bash
   ssh user@your-pi-address
   ```

2. **Create project folder in /var/www**
   ```bash
   sudo mkdir -p /var/www/ollama_chatbot
   cd /var/www/ollama_chatbot
   ```

3. **Copy docker-compose.yml to Pi**
   
   **Option A - Copy to home, then move:**
   ```bash
   # On your Mac
   scp docker-compose.yml user@your-pi:~/
   
   # On Pi
   sudo mv ~/docker-compose.yml /var/www/ollama_chatbot/
   ```
   
   **Option B - Copy-paste with nano:**
   ```bash
   # On Pi
   sudo nano /var/www/ollama_chatbot/docker-compose.yml
   # Paste the content from your Mac
   ```

4. **Start the services**
   ```bash
   sudo docker-compose up -d
   ```

5. **Check if container is running**
   ```bash
   docker-compose ps
   docker logs ollama-gemma -f
   ```
   
   **Note:** First startup takes 5-10 minutes to download the Gemma-2-2b model (~1.6GB)

6. **Connect WhatsApp (Detailed Steps)**

   ### Prerequisites on Pi:
   - Docker and Docker Compose installed ✅
   - Container running: `docker ps` should show `ollama-gemma`
   - SSH access working
   
   ### Step-by-Step QR Code Access:

   **Method 1: SSH Tunnel (Recommended - Most Secure)**
   
   This method creates a secure encrypted tunnel from your Mac to the Pi.
   
   a. **Open Terminal on your Mac** and run:
   ```bash
   ssh -L 3000:localhost:3000 user@your-pi-ip
   ```
   
   Example:
   ```bash
   ssh -L 3000:localhost:3000 gon.munillag@192.168.1.100
   ```
   
   What this does:
   - `-L 3000:localhost:3000` = Forward local port 3000 to Pi's localhost:3000
   - Creates encrypted tunnel through SSH
   - **Keep this terminal window open!**
   
   b. **Open your web browser** (Chrome, Firefox, Safari) and go to:
   ```
   http://localhost:3000/qr
   ```
   
   You should see the QR code appear!
   
   c. **If you see "This site can't be reached":**
   - Check the SSH terminal is still open
   - Make sure Docker container is running: `docker ps` on Pi
   - Check logs: `docker logs ollama-gemma -f` on Pi
   - Wait 1-2 minutes for WhatsApp bridge to fully start
   
   ---
   
   **Method 2: Direct Network Access (Temporary)**
   
   Use this if SSH tunnel doesn't work for some reason.
   
   a. **On Pi, edit docker-compose.yml:**
   ```bash
   cd /var/www/ollama_chatbot
   sudo nano docker-compose.yml
   ```
   
   b. **Change line 17 from:**
   ```yaml
   - "127.0.0.1:3000:3000"   # WhatsApp QR (localhost only)
   ```
   
   **To:**
   ```yaml
   - "3000:3000"   # WhatsApp QR (network accessible - TEMPORARY!)
   ```
   
   c. **Restart the container:**
   ```bash
   sudo docker-compose down
   sudo docker-compose up -d
   ```
   
   d. **Find your Pi's IP address** (if you don't know it):
   ```bash
   hostname -I
   ```
   
   e. **Open browser on your Mac/phone** and visit:
   ```
   http://YOUR_PI_IP:3000/qr
   ```
   Example: `http://192.168.1.100:3000/qr`
   
   f. **IMPORTANT: After scanning, secure it again!**
   ```bash
   # Edit docker-compose.yml and change back to:
   - "127.0.0.1:3000:3000"
   
   # Restart:
   sudo docker-compose down && sudo docker-compose up -d
   ```
   
   ---
   
   ### Scan the QR Code with WhatsApp:
   
   Once you can see the QR code in your browser:
   
   1. **Open WhatsApp on your phone**
   2. **Android:** Tap ⋮ (three dots) → **Linked Devices**
      **iPhone:** Tap **Settings** → **Linked Devices**
   3. Tap **Link a Device**
   4. **Scan the QR code** on your computer screen
   5. **Wait 5-10 seconds** - Page will show "✅ WhatsApp Connected!"
   
   ### Test the Bot:
   
   Send a message to yourself (your own WhatsApp number):
   ```
   You: What is the capital of France?
   Bot: The capital of France is Paris. It is located...
   ```
   
   **Note:** First response may take 30-60 seconds while model loads. Subsequent responses are faster (5-30 seconds).
   
   ### Troubleshooting QR Code Access:
   
   **Can't see QR code?**
   ```bash
   # On Pi - check if container is running
   docker ps | grep ollama-gemma
   
   # Check logs for errors
   docker logs ollama-gemma -f
   
   # Look for this line in logs:
   # "WhatsApp Bridge running on port 3000"
   ```
   
   **SSH tunnel not working?**
   - Make sure port 3000 isn't already in use on your Mac: `lsof -i :3000`
   - Try a different port: `ssh -L 3001:localhost:3000 user@pi` then visit `http://localhost:3001/qr`
   - Check Pi firewall: `sudo ufw status` (should show inactive or allow SSH)
   
   **QR code expired?**
   - Refresh the page: `http://localhost:3000/qr`
   - QR codes expire after a few minutes for security
   
   **Container keeps restarting?**
   ```bash
   # Check what's wrong
   docker logs ollama-gemma --tail 50
   
   # Common issue: Out of memory (need at least 4GB RAM)
   free -h
   ```

---

### 💬 WhatsApp Usage

**Features:**
- ✅ Works in personal chats
- ✅ Shows typing indicator while thinking
- ✅ Persistent session (no re-scan after restart)
- ✅ 2-minute timeout per message
- ⏱️ Responses take 5-30 seconds (Gemma on Pi is slower)

**Security:**
- 🔒 Port 3000 is bound to localhost only (can't be accessed from network)
- 🔒 Use SSH tunnel to safely access QR code
- 🔒 WhatsApp session is stored in encrypted Docker volume
- 🔒 Only you (who scanned QR) can use the bot

**Troubleshooting:**

*QR code not showing?*
```bash
docker logs ollama-gemma -f
```

*WhatsApp disconnects?*
```bash
# Remove session and re-scan
cd /var/www/ollama_chatbot
sudo docker-compose down
sudo docker volume rm ollama_chatbot_whatsapp-data
sudo docker-compose up -d
# Access QR code again with SSH tunnel or direct method
```

*Bot not responding?*
```bash
# Check if services are running
curl http://localhost:8000/health
curl http://localhost:3000/health
```

---

### Step 3: Updates (Automatic with Watchtower)

**With Watchtower running:**
- Just run `./build-and-push.sh` on your Mac
- Watchtower automatically pulls the new image on your Pi
- Container restarts with the new version
- **No manual intervention needed!** ✨

**Without Watchtower (Manual):**
```bash
# On Pi
cd /var/www/ollama_chatbot
sudo docker-compose pull
sudo docker-compose up -d
```

---

## 🧪 Testing

### Test the FastAPI endpoints

1. **Health check**
   ```bash
   curl http://localhost:8000/health
   ```

2. **List models**
   ```bash
   curl http://localhost:8000/models
   ```

3. **Send a chat message**
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{
       "message": "What is the capital of France?",
       "temperature": 0.7,
       "max_tokens": 100
     }'
   ```

### Expected Response:
```json
{
  "response": "The capital of France is Paris...",
  "model": "gemma2:2b",
  "done": true
}
```

---

## 🌐 API Documentation

### Endpoints

#### `GET /`
- **Description:** API status and available endpoints
- **Response:** JSON with API information

#### `GET /health`
- **Description:** Health check for both FastAPI and Ollama
- **Response:** 
  ```json
  {
    "status": "healthy",
    "fastapi": "running",
    "ollama": "running"
  }
  ```

#### `GET /models`
- **Description:** List available models in Ollama
- **Response:** List of installed models

#### `POST /chat`
- **Description:** Send a message to the chatbot
- **Request Body:**
  ```json
  {
    "message": "Your question here",
    "stream": false,
    "temperature": 0.7,
    "max_tokens": 500
  }
  ```
- **Response:**
  ```json
  {
    "response": "AI response here",
    "model": "gemma2:2b",
    "done": true
  }
  ```

**Parameters:**
- `message` (required): Your question/prompt
- `stream` (optional): Stream response word-by-word (default: false)
- `temperature` (optional): Creativity 0.0-1.0 (default: 0.7)
- `max_tokens` (optional): Max response length (default: 500)

---

## 🔧 Useful Commands

### On Mac (Build Machine)

```bash
# Rebuild and push new version
./build-and-push.sh

# Build without pushing (testing)
docker build --platform linux/arm64 -t test-image .
```

### On Raspberry Pi

```bash
# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Stop service
docker-compose down

# Stop and remove volumes (deletes model)
docker-compose down -v

# Pull latest image
docker-compose pull

# Update and restart
docker-compose pull && docker-compose up -d

# Check container status
docker-compose ps

# Enter container shell (debugging)
docker exec -it ollama-gemma /bin/bash
```

---

## 🔐 Cloudflare Tunnel Setup (Coming Next)

This will be covered in the deployment guide, but the tunnel will:
- Point to `http://localhost:8000`
- Provide HTTPS access from anywhere
- No port forwarding needed
- No firewall changes required

---

## 📊 Resource Usage

**Expected on Raspberry Pi 5 (8GB RAM):**
- **RAM:** ~3-4GB (model loaded)
- **Disk:** ~2GB (Docker image + model)
- **CPU:** Varies by usage (idle is minimal)

---

## 🐛 Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Common issues:
# - Out of memory: Gemma-2-2b needs at least 3GB RAM
# - Port conflict: Check if ports 8000/11434 are in use
```

### Model download fails
```bash
# Check internet connection
# Manually pull model:
docker exec -it ollama-gemma ollama pull gemma2:2b
```

### API not responding
```bash
# Check if both services are running
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8000/health      # FastAPI
```

### Health check failing
```bash
# Wait 60 seconds after startup (model download time)
# Check logs for errors:
docker-compose logs -f
```

---


## 🔄 CI/CD Pipeline

**Current Setup:**
1. **Mac M1 Pro** - Build multi-arch images
2. **Docker Hub** - Image registry
3. **Raspberry Pi** - Watchtower auto-pulls updates

**Workflow:**
```
Code Change → build-and-push.sh → Docker Hub → Watchtower (checks every 5 min) → Auto-Deploy
```

**How Watchtower Works:**
- Monitors running containers
- Checks Docker Hub every 5 minutes for image updates
- Compares image digest (hash) to detect new versions
- Automatically pulls, stops, and restarts with new image
- Cleans up old images

**Check if Watchtower is running:**
```bash
docker ps | grep watchtower
```

---

## 📚 Tech Stack

- **Ollama** - LLM runtime
- **Gemma-2-2b** - Google's 2B parameter model
- **FastAPI** - Python web framework
- **Uvicorn** - ASGI server
- **Docker** - Containerization
- **Docker Buildx** - Multi-architecture builds
- **Cloudflare Tunnel** - Secure external access

---

## 🤝 Contributing

Feel free to open issues or submit PRs!

---

## 📄 License

See LICENSE file for details.

---

## 🎯 Future Enhancements

Ideas for extending your chatbot:

1. **Conversation History** - Store chat history in database
2. **Multiple Users** - Support multiple WhatsApp numbers
3. **Group Chat Support** - Enable bot in WhatsApp groups
4. **Voice Messages** - Transcribe and respond to voice notes
5. **Image Understanding** - Add vision capabilities
6. **Custom Commands** - Add `/help`, `/reset`, etc.
7. **Rate Limiting** - Prevent spam/abuse
8. **Analytics** - Track usage and performance

---

## 💡 Tips

- **First startup is slow** - Model download takes time
- **Be patient** - Gemma-2-2b can take 5-30 seconds per response on Pi
- **Monitor RAM** - Use `docker stats` to check resource usage
- **Persistent storage** - Model is downloaded once and persists
- **Auto-restart enabled** - Service survives Pi reboots

---

**Enjoy your self-hosted AI chatbot!** 🚀

