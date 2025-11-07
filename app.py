"""
FastAPI Wrapper for Ollama - Gemma-2-2b Chatbot
This provides a simple REST API to interact with the Ollama service
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import logging
from typing import Optional

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app instance
app = FastAPI(
    title="Gemma-2-2b Chatbot API",
    description="API wrapper for Ollama running Gemma-2-2b on Raspberry Pi 5",
    version="1.0.0"
)

# Ollama API endpoint (running on same container)
OLLAMA_URL = "http://localhost:11434"

# Pydantic models for request/response validation
class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    stream: bool = False  # Whether to stream response or return all at once
    temperature: Optional[float] = 0.7  # Creativity (0.0-1.0)
    max_tokens: Optional[int] = 500  # Maximum response length

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    model: str
    done: bool


# Root endpoint - Health check
@app.get("/")
async def root():
    """
    Root endpoint to check if API is running
    Returns: Simple JSON message
    """
    return {
        "status": "online",
        "message": "Gemma-2-2b Chatbot API is running",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "models": "/models"
        }
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Check if both FastAPI and Ollama are healthy
    Returns: Health status of the service
    """
    try:
        # Try to connect to Ollama
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "fastapi": "running",
                    "ollama": "running"
                }
            else:
                return {
                    "status": "degraded",
                    "fastapi": "running",
                    "ollama": "error"
                }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Ollama service is not available"
        )


# List available models
@app.get("/models")
async def list_models():
    """
    Get list of models available in Ollama
    Returns: List of installed models
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )

@app.post("/send-whatsapp")
async def send_whatsapp(message: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://whatsapp:3000/send-message",
            json={"message": message}
        )
    return response.json()
# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to Gemma-2-2b and get a response
    
    Args:
        request: ChatRequest containing the message and parameters
    
    Returns:
        ChatResponse with the model's reply
    """
    try:
        # Prepare the request to Ollama
        ollama_request = {
            "model": "gemma2:2b",
            "prompt": request.message,
            "stream": request.stream,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }
        
        logger.info(f"Sending request to Ollama: {request.message[:50]}...")
        
        # Send request to Ollama
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=ollama_request
            )
            response.raise_for_status()
            
            # Parse Ollama's response
            result = response.json()
            
            logger.info(f"Received response from Ollama")
            
            return ChatResponse(
                response=result.get("response", ""),
                model=result.get("model", "gemma2:2b"),
                done=result.get("done", True)
            )
            
    except httpx.TimeoutException:
        logger.error("Request to Ollama timed out")
        raise HTTPException(
            status_code=504,
            detail="Request timed out. The model might be processing a long response."
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama returned error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ollama service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Run the app (for development/testing)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

