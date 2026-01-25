# =============================================================================
# Web Portal Server
# =============================================================================
#
# This is the backend server for the web chat portal. It:
#   1. Serves the chat UI (HTML page)
#   2. Handles user authentication (login)
#   3. Processes chat messages
#   4. Communicates with Ollama (AI) and Piper (TTS)
#
# TECHNOLOGY: FastAPI
# -------------------
# FastAPI is a modern Python web framework. It's:
#   - Fast (one of the fastest Python frameworks)
#   - Easy to write and read
#   - Automatically generates API documentation
#   - Has great support for async operations
#
# =============================================================================

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------
# Each import brings in functionality we need:

# os: Access environment variables (like passwords, URLs)
import os

# secrets: Generate secure random tokens for sessions
import secrets

# re: Regular expressions for pattern matching (stripping emojis)
import re

# datetime: Work with dates and times (session expiration)
from datetime import datetime, timedelta

# typing: Type hints for better code documentation
from typing import Optional

# FastAPI components:
# - FastAPI: The main application class
# - Request: Represents incoming HTTP requests
# - Response: Represents outgoing HTTP responses
# - HTTPException: For returning HTTP errors
# - Form: For handling form data (login form)
# - Depends: For dependency injection
from fastapi import FastAPI, Request, Response, HTTPException, Form, Depends

# FileResponse: Serve static files (HTML, CSS, JS)
# HTMLResponse: Return HTML content directly
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# StaticFiles: Mount a directory to serve static files
from fastapi.staticfiles import StaticFiles

# Cookie: Handle HTTP cookies for sessions
from fastapi import Cookie

# requests: Make HTTP calls to other services (Ollama, Piper)
import requests

# json: Parse and create JSON data
import json

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# These values control how the server behaves.
# They're read from environment variables, with fallback defaults.
#
# Environment variables are set in docker-compose.yml or .env file.
# This allows changing settings without modifying code.

# PORTAL_PASSWORD: The password users must enter to access the chat
# os.getenv("NAME", "default"): Get env var NAME, or use "default" if not set
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "prometheus")

# OLLAMA_URL: Where to send chat messages for AI processing
# Inside Docker network, services can reach each other by container name
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:8000")

# TTS_URL: Where to send text for speech synthesis
TTS_URL = os.getenv("TTS_URL", "http://piper-tts:5000")

# SESSION_SECRET: Secret key for signing session tokens
# secrets.token_hex(32): Generate a random 64-character hex string
# This is regenerated on each container restart (logs everyone out)
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

# SESSION_DURATION_HOURS: How long a login session lasts
SESSION_DURATION_HOURS = 24

# TTS_TRIGGER: The keyword that triggers voice output
# If a message starts with this word, the AI response will be spoken
TTS_TRIGGER = "speak"

# -----------------------------------------------------------------------------
# SESSION STORAGE
# -----------------------------------------------------------------------------
# In-memory storage for active sessions.
# Key: session token (string)
# Value: expiration time (datetime)
#
# NOTE: This is simple but not persistent. If the container restarts,
# all sessions are lost and users must log in again.
# For production, you might use Redis or a database.
active_sessions: dict[str, datetime] = {}

# -----------------------------------------------------------------------------
# FASTAPI APPLICATION
# -----------------------------------------------------------------------------
# Create the FastAPI application instance.
#
# title: Name shown in API documentation
# description: Description shown in API documentation
# version: API version number
app = FastAPI(
    title="Prometheus Web Portal",
    description="Chat interface for your AI assistant",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def strip_emojis_and_formatting(text: str) -> str:
    """
    Remove emojis, emoji descriptions, and markdown formatting from text.
    
    This is used before sending text to the TTS service because:
    - Emojis can't be spoken and might cause errors
    - Text descriptions of emojis (like "smiley face") sound awkward
    - Markdown symbols (*bold*, _italic_) would be read literally
    
    Args:
        text: The original text with possible emojis/formatting
        
    Returns:
        Clean text suitable for text-to-speech
    """
    # Regex pattern to match most emojis
    # \u00a9, \u00ae: Copyright and registered trademark symbols
    # \u2000-\u3300: Various symbols and punctuation
    # \ud83c[\ud000-\udfff]: Emoji range 1 (flags, etc.)
    # \ud83d[\ud000-\udfff]: Emoji range 2 (faces, objects)
    # \ud83e[\ud000-\udfff]: Emoji range 3 (newer emojis)
    emoji_pattern = re.compile(
        "(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|"
        "\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])"
    )
    
    # Remove emojis
    text = emoji_pattern.sub('', text)
    
    # Remove common emoji text descriptions that AI might write
    # This catches patterns like "smiling face with smiling eyes"
    # Case-insensitive matching
    emoji_descriptions = [
        # Faces with variations (catches "smiling face with smiling eyes", etc.)
        r'\bsmiling face with \w+ eyes\b',
        r'\bface with tears of joy\b',
        r'\bface with \w+ eyes\b',
        r'\bsmiley face\b', r'\bsmiling face\b', r'\bhappy face\b',
        r'\bsad face\b', r'\bcrying face\b', r'\bwinking face\b',
        r'\bthinking face\b', r'\blaughing face\b', r'\bgrinning face\b',
        r'\bbeaming face\b', r'\brelieved face\b', r'\bpensive face\b',
        r'\bconfused face\b', r'\bworried face\b', r'\bangry face\b',
        # Emoji keyword (only when followed by "emoji")
        r'\b\w+ emoji\b',  # "fire emoji", "heart emoji", etc.
        # Hands and gestures
        r'\bthumbs up\b', r'\bthumbs down\b', r'\bclapping hands\b', 
        r'\bwaving hand\b', r'\braised hands\b', r'\bfolded hands\b',
        # Objects and symbols (only obvious emoji descriptions)
        r'\bparty popper\b', r'\bcheck mark\b', r'\bcross mark\b',
        r'\bspeech bubble\b', r'\blight bulb\b', r'\bsparkles\b',
    ]
    for pattern in emoji_descriptions:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Remove markdown formatting characters
    # * = bold, _ = italic, ` = code, ~ = strikethrough
    text = re.sub(r'[*_`~]', '', text)
    
    # Collapse multiple spaces into one and trim
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def create_session_token() -> str:
    """
    Generate a secure random session token.
    
    Returns:
        A 64-character hexadecimal string
    """
    return secrets.token_hex(32)


def is_session_valid(token: Optional[str]) -> bool:
    """
    Check if a session token is valid and not expired.
    
    Args:
        token: The session token to check (might be None)
        
    Returns:
        True if the session is valid, False otherwise
    """
    # No token provided
    if not token:
        return False
    
    # Token not in our active sessions
    if token not in active_sessions:
        return False
    
    # Check if session has expired
    expiration = active_sessions[token]
    if datetime.now() > expiration:
        # Clean up expired session
        del active_sessions[token]
        return False
    
    return True


def call_ollama(message: str, for_speech: bool = False) -> str:
    """
    Send a message to Ollama and get the AI response.
    
    Args:
        message: The user's message to send to the AI
        for_speech: If True, instruct AI to avoid emojis (for TTS)
        
    Returns:
        The AI's response text
        
    Raises:
        HTTPException: If Ollama is unreachable or returns an error
    """
    try:
        # If this will be spoken, add instruction to avoid emojis
        if for_speech:
            message = f"{message}\n\n(Respond without any emojis, emoticons, or emoji descriptions. Keep it plain text only.)"
        
        # Make POST request to Ollama's chat endpoint
        response = requests.post(
            f"{OLLAMA_URL}/chat",  # URL: http://ollama:8000/chat
            json={"message": message},  # Send message as JSON
            timeout=120  # Wait up to 120 seconds (AI can be slow)
        )
        
        # Check if request was successful (status code 200-299)
        response.raise_for_status()
        
        # Parse JSON response and extract the reply
        data = response.json()
        return data.get("response", "No response from AI")
        
    except requests.exceptions.ConnectionError:
        # Ollama container is not reachable
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable. Is Ollama running?"
        )
    except requests.exceptions.Timeout:
        # Request took too long
        raise HTTPException(
            status_code=504,
            detail="AI service timeout. Try a shorter message."
        )
    except Exception as e:
        # Any other error
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with AI: {str(e)}"
        )


def call_tts(text: str) -> bool:
    """
    Send text to Piper TTS to be spoken through the Pi's speaker.
    
    Args:
        text: The text to speak
        
    Returns:
        True if TTS was successful, False otherwise
    """
    try:
        # Clean the text before sending to TTS
        clean_text = strip_emojis_and_formatting(text)
        
        # Make POST request to Piper's speak endpoint
        response = requests.post(
            f"{TTS_URL}/speak",  # URL: http://piper-tts:5000/speak
            json={"text": clean_text},  # Send cleaned text as JSON
            timeout=30  # Wait up to 30 seconds
        )
        
        # Check if request was successful
        return response.status_code == 200
        
    except Exception as e:
        # Log error but don't crash - TTS is optional
        print(f"TTS error: {e}")
        return False


# -----------------------------------------------------------------------------
# ROUTES (ENDPOINTS)
# -----------------------------------------------------------------------------
# Routes define what happens when someone visits a URL.
# Each @app.get or @app.post decorator maps a URL to a function.

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Docker uses this to verify the container is running properly.
    Returns a simple JSON response indicating the server is alive.
    
    URL: GET /health
    """
    return {"status": "healthy", "service": "web-portal"}


@app.get("/")
async def root(session: Optional[str] = Cookie(None)):
    """
    Main page - redirects to login or chat based on session.
    
    Cookie(None): Extracts the 'session' cookie from the request.
    If no cookie exists, session will be None.
    
    URL: GET /
    """
    if is_session_valid(session):
        # User is logged in, show the chat page
        return FileResponse("static/index.html")
    else:
        # User is not logged in, show login form
        return HTMLResponse(content=get_login_page())


@app.get("/login")
async def login_page():
    """
    Show the login page.
    
    URL: GET /login
    """
    return HTMLResponse(content=get_login_page())


@app.post("/login")
async def login(response: Response, password: str = Form(...)):
    """
    Process login form submission.
    
    Args:
        response: The response object (used to set cookies)
        password: The password from the form (Form(...) means required)
        
    URL: POST /login
    """
    # Check if password matches
    if password != PORTAL_PASSWORD:
        return HTMLResponse(
            content=get_login_page(error="Invalid password"),
            status_code=401
        )
    
    # Create new session
    token = create_session_token()
    expiration = datetime.now() + timedelta(hours=SESSION_DURATION_HOURS)
    active_sessions[token] = expiration
    
    # Create response that redirects to home page
    redirect_response = HTMLResponse(
        content="<script>window.location.href='/';</script>",
        status_code=200
    )
    
    # Set session cookie
    # httponly=True: Cookie can't be accessed by JavaScript (security)
    # max_age: Cookie expires after this many seconds
    # samesite="lax": Cookie sent with same-site requests (security)
    redirect_response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        max_age=SESSION_DURATION_HOURS * 3600,  # Convert hours to seconds
        samesite="lax"
    )
    
    return redirect_response


@app.post("/logout")
async def logout(response: Response, session: Optional[str] = Cookie(None)):
    """
    Log out the user by invalidating their session.
    
    URL: POST /logout
    """
    # Remove session from active sessions
    if session and session in active_sessions:
        del active_sessions[session]
    
    # Create response
    redirect_response = JSONResponse(content={"status": "logged out"})
    
    # Delete the session cookie by setting it to empty with max_age=0
    redirect_response.delete_cookie(key="session")
    
    return redirect_response


@app.post("/chat")
async def chat(request: Request, session: Optional[str] = Cookie(None)):
    """
    Process a chat message and return AI response.
    
    This is the main endpoint that:
    1. Receives user message
    2. Checks for "speak" keyword
    3. Calls Ollama for AI response
    4. Optionally calls Piper TTS
    5. Returns the response
    
    URL: POST /chat
    Body: {"message": "your message here"}
    """
    # Check if user is logged in
    if not is_session_valid(session):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Parse the JSON body
    try:
        body = await request.json()
        message = body.get("message", "").strip()
    except:
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    # Don't process empty messages
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Check if user wants voice output
    # Message format: "speak What is the weather?"
    should_speak = False
    if message.lower().startswith(TTS_TRIGGER):
        should_speak = True
        # Remove the trigger word from the message
        # "speak hello" becomes "hello"
        message = message[len(TTS_TRIGGER):].strip()
    
    # Get AI response (tell AI to avoid emojis if speaking)
    ai_response = call_ollama(message, for_speech=should_speak)
    
    # If "speak" was used, send response to TTS
    tts_success = False
    if should_speak:
        tts_success = call_tts(ai_response)
    
    # Return response to browser
    return {
        "response": ai_response,
        "spoken": tts_success,  # Let frontend know if TTS was used
        "should_speak": should_speak
    }


# -----------------------------------------------------------------------------
# LOGIN PAGE HTML
# -----------------------------------------------------------------------------
def get_login_page(error: str = None) -> str:
    """
    Generate the HTML for the login page.
    
    Args:
        error: Optional error message to display
        
    Returns:
        Complete HTML string for the login page
    """
    error_html = ""
    if error:
        error_html = f'<div class="error">{error}</div>'
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Prometheus</title>
    <style>
        /* ---------- CSS RESET AND BASE STYLES ---------- */
        /* Remove default margins and use border-box sizing */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        /* Body styling - dark theme like ChatGPT */
        body {{
            font-family: 'Söhne', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background-color: #212121;
            color: #ececec;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        
        /* Login container */
        .login-container {{
            background-color: #2f2f2f;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
            width: 100%;
            max-width: 400px;
            text-align: center;
        }}
        
        /* Title */
        h1 {{
            font-size: 28px;
            margin-bottom: 8px;
            color: #ececec;
        }}
        
        /* Subtitle */
        .subtitle {{
            color: #8e8e8e;
            margin-bottom: 32px;
            font-size: 14px;
        }}
        
        /* Form styling */
        form {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        /* Password input field */
        input[type="password"] {{
            padding: 14px 16px;
            border: 1px solid #4a4a4a;
            border-radius: 8px;
            background-color: #3a3a3a;
            color: #ececec;
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
        }}
        
        input[type="password"]:focus {{
            border-color: #10a37f;
        }}
        
        /* Submit button */
        button {{
            padding: 14px 16px;
            border: none;
            border-radius: 8px;
            background-color: #10a37f;
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        
        button:hover {{
            background-color: #0e906f;
        }}
        
        /* Error message */
        .error {{
            background-color: #ff4444;
            color: white;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 16px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔥 Prometheus</h1>
        <p class="subtitle">Enter password to access your AI assistant</p>
        {error_html}
        <form method="post" action="/login">
            <input type="password" name="password" placeholder="Password" required autofocus>
            <button type="submit">Continue</button>
        </form>
    </div>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# STATIC FILES
# -----------------------------------------------------------------------------
# Mount the static directory to serve index.html and other static files
# This must be done after all other routes are defined
# Because FastAPI processes routes in order, and "/" in static would catch all
#
# Note: We handle "/" explicitly above, so static files are served at /static/
# But the main page at "/" uses FileResponse for the logged-in chat UI
# -----------------------------------------------------------------------------

# This line is intentionally commented out because we serve index.html explicitly
# app.mount("/static", StaticFiles(directory="static"), name="static")


# -----------------------------------------------------------------------------
# STARTUP MESSAGE
# -----------------------------------------------------------------------------
# This runs when the server starts (optional, for debugging)
@app.on_event("startup")
async def startup_event():
    """
    Called when the server starts up.
    Prints configuration info for debugging.
    """
    print("=" * 60)
    print("🌐 Web Portal Starting...")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"TTS URL: {TTS_URL}")
    print(f"Session duration: {SESSION_DURATION_HOURS} hours")
    print(f"TTS trigger word: '{TTS_TRIGGER}'")
    print("=" * 60)

