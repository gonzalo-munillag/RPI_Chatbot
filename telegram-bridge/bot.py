#!/usr/bin/env python3
"""
=============================================================================
Telegram Bridge for Prometheus AI
=============================================================================

This bot connects Telegram to the Ollama AI backend, with optional TTS support.

Features:
    - Responds to direct messages from authorized users
    - "speak" keyword triggers TTS output
    - Conversation context (memory of recent messages)
    - Rate limiting to prevent abuse

Environment Variables:
    TELEGRAM_BOT_TOKEN  - Bot token from @BotFather (required)
    AUTHORIZED_USERS    - Comma-separated Telegram user IDs (required)
    OLLAMA_URL          - Ollama API URL (default: http://ollama:8000)
    TTS_URL             - Piper TTS URL (default: http://piper-tts:5000)
    MAX_CONTEXT_MESSAGES - Max messages to keep in context (default: 10)

Usage:
    python bot.py

=============================================================================
"""

import os
import re
import logging
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Telegram Bot Token (from @BotFather)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Authorized user IDs (comma-separated)
# Get your ID by messaging @userinfobot on Telegram
AUTHORIZED_USERS_STR = os.getenv("AUTHORIZED_USERS", "")
AUTHORIZED_USERS = set()
if AUTHORIZED_USERS_STR:
    AUTHORIZED_USERS = {int(uid.strip()) for uid in AUTHORIZED_USERS_STR.split(",") if uid.strip()}

# Authorized group IDs (comma-separated, optional)
# If set, bot will only stay in these groups and leave others
# Get group ID by adding @getidsbot to your group
AUTHORIZED_GROUPS_STR = os.getenv("AUTHORIZED_GROUPS", "")
AUTHORIZED_GROUPS = set()
if AUTHORIZED_GROUPS_STR:
    AUTHORIZED_GROUPS = {int(gid.strip()) for gid in AUTHORIZED_GROUPS_STR.split(",") if gid.strip()}

# Backend URLs
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:8000")
TTS_URL = os.getenv("TTS_URL", "http://piper-tts:5000")

# Context settings
MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "10"))

# Rate limiting
RATE_LIMIT_MESSAGES = 10  # Max messages per window
RATE_LIMIT_WINDOW = 60    # Window in seconds

# TTS trigger keyword
TTS_TRIGGER = "speak"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

# Conversation context per user
conversation_contexts: dict[int, list[dict]] = defaultdict(list)

# Rate limiting tracker
rate_limit_tracker: dict[int, list[datetime]] = defaultdict(list)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    # If no authorized users configured, allow everyone (not recommended)
    if not AUTHORIZED_USERS:
        logger.warning("No AUTHORIZED_USERS configured - allowing all users!")
        return True
    return user_id in AUTHORIZED_USERS


def check_rate_limit(user_id: int) -> bool:
    """
    Check if user has exceeded rate limit.
    Returns True if within limit, False if exceeded.
    """
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    # Clean old entries
    rate_limit_tracker[user_id] = [
        ts for ts in rate_limit_tracker[user_id] if ts > window_start
    ]
    
    # Check limit
    if len(rate_limit_tracker[user_id]) >= RATE_LIMIT_MESSAGES:
        return False
    
    # Add current request
    rate_limit_tracker[user_id].append(now)
    return True


def add_to_context(user_id: int, role: str, content: str):
    """Add a message to the user's conversation context."""
    conversation_contexts[user_id].append({
        "role": role,
        "content": content
    })
    
    # Trim to max context size
    if len(conversation_contexts[user_id]) > MAX_CONTEXT_MESSAGES:
        conversation_contexts[user_id] = conversation_contexts[user_id][-MAX_CONTEXT_MESSAGES:]


def get_context(user_id: int) -> list[dict]:
    """Get the conversation context for a user."""
    return conversation_contexts[user_id].copy()


def clear_context(user_id: int):
    """Clear a user's conversation context."""
    conversation_contexts[user_id] = []


def strip_emojis_and_formatting(text: str) -> str:
    """
    Remove emojis and markdown formatting for TTS.
    """
    # Unicode emoji pattern
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)
    
    # Remove markdown formatting
    text = re.sub(r'[*_`~]', '', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# =============================================================================
# AI BACKEND COMMUNICATION
# =============================================================================

async def query_ollama(message: str, context: list[dict]) -> str:
    """
    Send a message to the Ollama backend and get a response.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Build the full message with context
            payload = {
                "message": message,
                "context": context
            }
            
            response = await client.post(
                f"{OLLAMA_URL}/chat",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("response", "I couldn't generate a response.")
            
    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        return "I'm taking too long to think. Please try again."
    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error: {e}")
        return "I'm having trouble connecting to my brain. Please try again later."
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return "Something went wrong. Please try again."


async def speak_via_tts(text: str) -> bool:
    """
    Send text to Piper TTS to be spoken aloud.
    Returns True if successful.
    """
    try:
        clean_text = strip_emojis_and_formatting(text)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{TTS_URL}/speak",
                json={"text": clean_text}
            )
            response.raise_for_status()
            
            logger.info(f"TTS spoke: {clean_text[:50]}...")
            return True
            
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return False


# =============================================================================
# TELEGRAM HANDLERS
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    user_id = user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            f"⛔ You are not authorized to use this bot.\n"
            f"Your user ID is: {user_id}\n"
            f"Ask the admin to add you to the authorized users list."
        )
        logger.warning(f"Unauthorized /start from user {user_id} ({user.username})")
        return
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm Prometheus, your private AI assistant.\n\n"
        f"Just send me a message and I'll respond.\n\n"
        f"Commands:\n"
        f"• /clear - Clear conversation history\n"
        f"• /help - Show this message\n\n"
        f"Tips:\n"
        f"• Start your message with 'speak' to have me say the response aloud 🔊"
    )
    logger.info(f"User {user_id} ({user.username}) started the bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start_command(update, context)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - clears conversation context."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return
    
    clear_context(user_id)
    await update.message.reply_text("🧹 Conversation history cleared!")
    logger.info(f"User {user_id} cleared context")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text
    chat = update.effective_chat
    
    # Check if this is a group chat
    is_group = chat.type in ["group", "supergroup"]
    
    # In groups, only respond if bot is mentioned or message starts with bot name
    if is_group:
        bot_username = context.bot.username.lower()
        message_lower = message_text.lower()
        
        # Check if bot is mentioned (@botname) or message starts with "prometheus"
        is_mentioned = f"@{bot_username}" in message_lower
        starts_with_trigger = message_lower.startswith("prometheus")
        
        if not is_mentioned and not starts_with_trigger:
            # Ignore message - not directed at bot
            return
        
        # Remove the mention/trigger from the message
        if is_mentioned:
            message_text = re.sub(rf"@{bot_username}\s*", "", message_text, flags=re.IGNORECASE).strip()
        elif starts_with_trigger:
            message_text = re.sub(r"^prometheus\s*", "", message_text, flags=re.IGNORECASE).strip()
        
        if not message_text:
            await update.message.reply_text("Yes? How can I help?")
            return
    
    # Check authorization
    if not is_authorized(user_id):
        if is_group:
            # In groups, silently ignore unauthorized users
            logger.warning(f"Unauthorized group message from {user_id}: {message_text[:50]}")
            return
        await update.message.reply_text(
            f"⛔ You are not authorized.\nYour ID: {user_id}"
        )
        logger.warning(f"Unauthorized message from {user_id}: {message_text[:50]}")
        return
    
    # Check rate limit
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⏳ You're sending messages too fast. Please wait a moment."
        )
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return
    
    # Check for TTS trigger
    should_speak = False
    if message_text.lower().startswith(TTS_TRIGGER):
        should_speak = True
        message_text = message_text[len(TTS_TRIGGER):].strip()
        if not message_text:
            await update.message.reply_text("Please include a message after 'speak'")
            return
    
    logger.info(f"{'[Group] ' if is_group else ''}User {user_id}: {message_text[:50]}{'...' if len(message_text) > 50 else ''}")
    
    # Show typing indicator
    await update.message.chat.send_action("typing")
    
    # Get conversation context
    ctx = get_context(user_id)
    
    # Add user message to context
    add_to_context(user_id, "user", message_text)
    
    # Query AI
    response = await query_ollama(message_text, ctx)
    
    # Add AI response to context
    add_to_context(user_id, "assistant", response)
    
    # Send response
    await update.message.reply_text(response)
    
    # Speak if requested
    if should_speak:
        success = await speak_via_tts(response)
        if success:
            await update.message.reply_text("🔊 (spoken)")
        else:
            await update.message.reply_text("⚠️ Couldn't speak the response")
    
    logger.info(f"Responded to {user_id}: {response[:50]}{'...' if len(response) > 50 else ''}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle when bot is added to or removed from a group.
    If AUTHORIZED_GROUPS is set, auto-leave unauthorized groups.
    """
    if not update.my_chat_member:
        return
    
    chat = update.my_chat_member.chat
    new_status = update.my_chat_member.new_chat_member.status
    
    # Only care about group/supergroup
    if chat.type not in ["group", "supergroup"]:
        return
    
    # Bot was added to a group
    if new_status in ["member", "administrator"]:
        # If AUTHORIZED_GROUPS is set, check if this group is allowed
        if AUTHORIZED_GROUPS and chat.id not in AUTHORIZED_GROUPS:
            logger.warning(f"🚫 Leaving unauthorized group: {chat.title} (ID: {chat.id})")
            try:
                await context.bot.send_message(
                    chat.id,
                    "⛔ Sorry, I'm not authorized to operate in this group.\n"
                    f"Group ID: {chat.id}\n"
                    "Ask my admin to add this group to the authorized list."
                )
                await context.bot.leave_chat(chat.id)
            except Exception as e:
                logger.error(f"Failed to leave group {chat.id}: {e}")
        else:
            logger.info(f"✅ Joined group: {chat.title} (ID: {chat.id})")
            if AUTHORIZED_GROUPS:
                await context.bot.send_message(
                    chat.id,
                    "👋 Hello! I'm Prometheus, your AI assistant.\n\n"
                    "Mention me with @botname or start your message with 'Prometheus' to chat!"
                )


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Start the bot."""
    logger.info("=" * 60)
    logger.info("🤖 Prometheus Telegram Bot Starting")
    logger.info("=" * 60)
    logger.info(f"Ollama URL: {OLLAMA_URL}")
    logger.info(f"TTS URL: {TTS_URL}")
    logger.info(f"Authorized users: {AUTHORIZED_USERS if AUTHORIZED_USERS else 'ALL (not recommended)'}")
    logger.info(f"Authorized groups: {AUTHORIZED_GROUPS if AUTHORIZED_GROUPS else 'ALL (not recommended for production)'}")
    logger.info(f"Max context messages: {MAX_CONTEXT_MESSAGES}")
    logger.info("=" * 60)
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Handle bot being added/removed from groups
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Start polling
    logger.info("🚀 Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

