# 🎨 Customization Guide

## Table of Contents
1. [Changing the System Prompt](#1-changing-the-system-prompt)
2. [Switching to a Different LLM](#2-switching-to-a-different-llm)
3. [Why `/var/www` for Projects?](#3-why-varwww-for-projects)

---

## 1. Changing the System Prompt

### What is a System Prompt?

A system prompt defines your AI's personality, behavior, and response style. It's like giving instructions to the AI before every conversation.

### Method 1: Edit `.env` file (Recommended - No Rebuild Required!)

On your Raspberry Pi:

```bash
cd /var/www/ollama_chatbot
sudo nano .env
```

Edit the `SYSTEM_PROMPT` line:

```bash
SYSTEM_PROMPT=You are a pirate captain who answers questions in pirate speak! Arrr!
```

Save (Ctrl+X, Y, Enter), then restart:
```bash
sudo docker-compose restart ollama
```

**Done! No rebuild needed.** 🎉

### Method 2: Edit `docker-compose.yml` (Alternative)

If you prefer, you can also set environment variables directly in `docker-compose.yml`, but using `.env` is cleaner and keeps all configuration in one place.

### Example System Prompts

**Concise Assistant:**
```
You are a helpful assistant. Keep responses under 100 words and very concise.
```

**Technical Expert:**
```
You are a senior software engineer. Provide detailed technical explanations with code examples when relevant. Assume the user has programming knowledge.
```

**Creative Writer:**
```
You are a creative writer who enjoys storytelling. When answering questions, weave in narrative elements and vivid descriptions.
```

**Friendly Tutor:**
```
You are a patient tutor explaining concepts to a beginner. Use simple language, analogies, and step-by-step explanations.
```

---

## 2. Switching to a Different LLM

### Available Models

Ollama supports many models. Check the [Ollama Library](https://ollama.com/library) for the full list. Here are popular options that work on Raspberry Pi:

| Model | Size | RAM Required | Speed | Best For |
|-------|------|-------------|-------|----------|
| `gemma2:2b` | 1.6GB | 3GB | Fast | General use, current default |
| `phi3:mini` | 2.3GB | 4GB | Fast | Reasoning, math |
| `llama3.2:3b` | 2.0GB | 4GB | Medium | Balanced performance |
| `mistral:7b` | 4.1GB | 8GB | Slower | High quality responses |
| `qwen2.5:3b` | 2.0GB | 4GB | Fast | Multilingual support |
| `deepseek-r1:1.5b` | 1.0GB | 2GB | Very fast | Lightweight, basic tasks |

### How to Switch Models

**On Your Raspberry Pi:**

1. **Edit `.env` file:**
   ```bash
   cd /var/www/ollama_chatbot
   sudo nano .env
   ```

2. **Change the `MODEL_NAME` line:**
   ```bash
   MODEL_NAME=llama3.2:3b   # Change this to any model
   ```

3. **Save and restart:**
   ```bash
   # Save: Ctrl+X, Y, Enter
   sudo docker-compose restart ollama
   ```

4. **Watch the logs** (model will download automatically):
   ```bash
   sudo docker logs ollama-gemma -f
   ```
   
   You'll see: `Pulling model: llama3.2:3b...`

5. **Wait for download** (3-10 minutes depending on model size)

**That's it!** No code changes, no rebuilding. The new model will be used automatically. 🚀

### Important Notes

- **RAM Requirement:** Make sure your Pi has enough RAM for the model
- **First Message Slow:** First message after switching will be slower (model loading)
- **Storage:** Old models stay in the volume. To clean up:
  ```bash
  docker exec -it ollama-gemma ollama rm gemma2:2b
  ```

### Testing Your New Model

Send a test message to the bot:
```
Prometheus, what model are you running?
```

---

## 3. Why `/var/www` for Projects?

### The Short Answer

**Historical convention** from web servers, but **not ideal** for non-web projects like this chatbot.

### The Long Answer

#### What is `/var/www`?

- `/var` = "variable data" (files that change)
- `/www` = web content (from Apache/Nginx days)
- Originally meant for HTML files served by web servers

#### Why We Used It

1. **Familiarity** - Web developers recognize it immediately
2. **Works fine** - There's no technical problem with using it
3. **Clear separation** - Keeps projects out of home directories

#### Better Alternatives

| Location | Pros | Cons | Best For |
|----------|------|------|----------|
| `/opt/ollama_chatbot` | ✅ Standard for add-on software<br>✅ Semantic correctness | ⚠️ Requires sudo | Production deployments |
| `/home/pi/ollama_chatbot` | ✅ No sudo needed<br>✅ Easy permissions | ⚠️ Tied to user account<br>⚠️ Deleted if user removed | Development, testing |
| `/srv/ollama_chatbot` | ✅ Meant for service data<br>✅ Clean separation | ⚠️ Less common<br>⚠️ Requires sudo | Data-heavy services |
| `/var/www/ollama_chatbot` | ✅ Works fine<br>✅ Familiar to web devs | ⚠️ Not semantically correct<br>⚠️ Requires sudo | Web-related projects |

### How to Move to `/opt` (Recommended)

If you want to move your project to the "correct" location:

```bash
# On Raspberry Pi
cd /var/www

# Stop services
sudo docker-compose -f ollama_chatbot/docker-compose.yml down

# Create /opt directory
sudo mkdir -p /opt/ollama_chatbot

# Copy files
sudo cp ollama_chatbot/docker-compose.yml /opt/ollama_chatbot/
sudo cp ollama_chatbot/.env /opt/ollama_chatbot/

# Move Docker volumes (optional - keeps existing data)
# Alternatively, just restart and re-scan WhatsApp QR

# Update references in scripts if any
cd /opt/ollama_chatbot

# Start services
sudo docker-compose up -d
```

**Update your README** to reflect the new path!

### The Bottom Line

- **`/var/www` works perfectly fine** - no need to change if already set up
- **`/opt` is more "correct"** - use it if starting fresh or you care about Linux conventions
- **`/home/pi` is easiest** - good for personal projects without sudo hassles

---

## Advanced Customization

### Combining System Prompt + Different Model

Simply edit your `.env` file with both settings:

```bash
# In /var/www/ollama_chatbot/.env
MODEL_NAME=mistral:7b
SYSTEM_PROMPT=You are a technical documentation expert. Provide clear, structured answers with code examples.
```

Then restart:
```bash
sudo docker-compose restart ollama
```

**That's it!** Both changes apply immediately.

### Temperature and Token Limits

These can be adjusted per-message via the API or set defaults in `app.py`:

```python
class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    temperature: float = 0.7  # Change default: 0.0 (deterministic) to 1.0 (creative)
    max_tokens: int = 500     # Change default response length
```

---

## Troubleshooting

### Model Download Fails
```bash
# Check internet connection
ping ollama.com

# Check available disk space
df -h

# Manually pull model
docker exec -it ollama-gemma ollama pull llama3.2:3b
```

### Bot Not Using New System Prompt
```bash
# Verify .env file has correct value
cd /var/www/ollama_chatbot
sudo cat .env | grep SYSTEM_PROMPT

# Restart container
sudo docker-compose restart ollama

# Check logs
sudo docker logs ollama-gemma -f

# Verify environment variable is loaded
docker exec -it ollama-gemma env | grep SYSTEM_PROMPT
```

### Out of Memory
- Choose a smaller model (e.g., `gemma2:2b` or `phi3:mini`)
- Check RAM usage: `free -h`
- Close other applications on Pi

---

**Happy customizing!** 🎨🤖

