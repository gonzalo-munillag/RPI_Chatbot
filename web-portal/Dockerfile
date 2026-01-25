# =============================================================================
# Web Portal Dockerfile
# =============================================================================
#
# This file tells Docker how to build the web portal container.
#
# WHAT IS A DOCKERFILE?
# ---------------------
# A Dockerfile is like a recipe. It lists all the steps needed to create
# a container image. Docker reads this file and executes each instruction
# in order, creating layers that form the final image.
#
# WHAT IS A CONTAINER?
# --------------------
# A container is like a lightweight virtual machine. It packages your
# application with all its dependencies so it runs the same everywhere.
#
# =============================================================================

# -----------------------------------------------------------------------------
# BASE IMAGE
# -----------------------------------------------------------------------------
# FROM: Specifies the starting point for our container.
# We use Python 3.11-slim which is:
#   - python:3.11 = Python version 3.11
#   - slim = Minimal installation (smaller image size)
#
# Think of this as: "Start with a computer that already has Python installed"
# -----------------------------------------------------------------------------
FROM python:3.11-slim

# -----------------------------------------------------------------------------
# WORKING DIRECTORY
# -----------------------------------------------------------------------------
# WORKDIR: Sets the directory where all subsequent commands will run.
# It's like doing "cd /app" at the start.
# If the directory doesn't exist, Docker creates it.
#
# All our application files will live in /app inside the container.
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# INSTALL SYSTEM DEPENDENCIES
# -----------------------------------------------------------------------------
# RUN: Executes a command during the build process.
#
# apt-get update: Refreshes the list of available packages
# apt-get install: Installs system packages
#   - curl: Command-line tool for making HTTP requests (used for health checks)
#
# rm -rf /var/lib/apt/lists/*: Cleans up package lists to reduce image size
#
# The && connects commands so they run in a single layer (more efficient)
# The \ allows us to break long commands across multiple lines
# -----------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# COPY REQUIREMENTS FILE
# -----------------------------------------------------------------------------
# COPY: Copies files from your computer into the container.
#
# We copy requirements.txt first (before the rest of the code) because:
#   - Docker caches each layer
#   - If requirements.txt hasn't changed, Docker reuses the cached layer
#   - This makes rebuilds faster when only code changes
#
# Format: COPY <source on your computer> <destination in container>
# -----------------------------------------------------------------------------
COPY web-portal/requirements.txt .

# -----------------------------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# -----------------------------------------------------------------------------
# pip install: Python's package installer
#
# --no-cache-dir: Don't save downloaded packages (reduces image size)
# -r requirements.txt: Install all packages listed in requirements.txt
#
# This installs: FastAPI, Uvicorn, Requests, etc.
# -----------------------------------------------------------------------------
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# COPY APPLICATION CODE
# -----------------------------------------------------------------------------
# Now we copy the rest of our application:
#   - server.py: The main FastAPI application
#   - static/: Directory containing HTML, CSS, JS files
#
# We copy these last because code changes more often than dependencies.
# This way, dependency installation is cached and not re-run on code changes.
# -----------------------------------------------------------------------------
COPY web-portal/server.py .
COPY web-portal/static/ ./static/

# -----------------------------------------------------------------------------
# EXPOSE PORT
# -----------------------------------------------------------------------------
# EXPOSE: Documents which port the container listens on.
#
# This doesn't actually open the port - it's just documentation.
# The actual port mapping happens in docker-compose.yml
#
# Port 5054 is where our FastAPI server will listen for requests.
# -----------------------------------------------------------------------------
EXPOSE 5054

# -----------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------
# HEALTHCHECK: Tells Docker how to check if the container is healthy.
#
# Docker will periodically run this command:
#   - If it returns 0 (success): Container is healthy
#   - If it returns non-zero: Container is unhealthy
#
# Options:
#   --interval=30s: Check every 30 seconds
#   --timeout=10s: Wait max 10 seconds for response
#   --start-period=5s: Wait 5 seconds before first check (app startup time)
#   --retries=3: Mark unhealthy after 3 consecutive failures
#
# curl -f: Fetch URL, fail silently on HTTP errors
# http://localhost:5054/health: Our health check endpoint
# || exit 1: If curl fails, exit with code 1 (unhealthy)
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5054/health || exit 1

# -----------------------------------------------------------------------------
# STARTUP COMMAND
# -----------------------------------------------------------------------------
# CMD: The command that runs when the container starts.
#
# uvicorn: ASGI server that runs our FastAPI app
# server:app: Run the 'app' object from 'server.py'
# --host 0.0.0.0: Listen on all network interfaces (not just localhost)
#                 This allows connections from outside the container
# --port 5054: Listen on port 5054
#
# Using JSON array format ["cmd", "arg1", "arg2"] is preferred over
# string format "cmd arg1 arg2" because it doesn't invoke a shell.
# -----------------------------------------------------------------------------
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5054"]

