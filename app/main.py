"""
TinyChat - A minimal FastAPI chatbot with OpenAI-compatible API support.

This application provides a web-based chat interface that connects to OpenAI-compatible
language model APIs. Features include:
- Server-Sent Events (SSE) for streaming responses
- Client-side conversation storage in browser localStorage
- Security hardening (input validation, security headers)
- Configurable models and parameters via environment variables
- Stateless backend architecture for horizontal scalability

Author: Jason A. Cox
License: MIT
GitHub: https://github.com/jasonacox/tinychat
"""
__version__ = "0.2.3"

# Standard library imports
import asyncio
import base64
import io
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, AsyncGenerator

# Third-party imports
import aiohttp
import httpx
from PIL import Image
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG for production
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tinychat")

# Configuration
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))

# Security Configuration
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "8000"))  # Max chars per message
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))  # Max messages per conversation
ENABLE_DEBUG_LOGS = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Research/Logging Configuration
CHAT_LOG = os.getenv("CHAT_LOG", "")  # Path to JSONL file for logging conversations

# Image Generation Configuration
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "swarmui").lower()  # swarmui or openai

# SwarmUI settings
SWARMUI = os.getenv("SWARMUI", "http://localhost:7801")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "Flux/flux1-schnell-fp8")
IMAGE_CFGSCALE = float(os.getenv("IMAGE_CFGSCALE", "1.0"))
IMAGE_STEPS = int(os.getenv("IMAGE_STEPS", "6"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1024"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "1024"))
IMAGE_SEED = int(os.getenv("IMAGE_SEED", "-1"))
IMAGE_TIMEOUT = int(os.getenv("IMAGE_TIMEOUT", "300"))

# OpenAI image settings
OPENAI_IMAGE_API_KEY = os.getenv("OPENAI_IMAGE_API_KEY", "")
OPENAI_IMAGE_API_BASE = os.getenv("OPENAI_IMAGE_API_BASE", "https://api.openai.com/v1")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
OPENAI_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")

# File lock for thread-safe logging
_log_lock = asyncio.Lock()

# Active streaming generations counter
_active_generations = 0
_generations_lock = asyncio.Lock()

# Page load tracking for session counting (session_id: timestamp)
_page_loads: Dict[str, datetime] = {}
_page_loads_lock = asyncio.Lock()
SESSION_TIMEOUT_MINUTES = 5  # Consider session inactive after 5 minutes

# Available models - can be set via environment variable as comma-separated list
AVAILABLE_MODELS = os.getenv("AVAILABLE_MODELS", f"{DEFAULT_MODEL},gpt-3.5-turbo,gpt-4,gpt-4-turbo").split(",")
# Remove duplicates and empty strings
AVAILABLE_MODELS = list(dict.fromkeys([model.strip() for model in AVAILABLE_MODELS if model.strip()]))

# Ensure DEFAULT_MODEL is in AVAILABLE_MODELS
if DEFAULT_MODEL not in AVAILABLE_MODELS:
    logger.warning(f"⚠️  Configuration issue: DEFAULT_MODEL '{DEFAULT_MODEL}' not in AVAILABLE_MODELS")
    logger.warning(f"   Adding '{DEFAULT_MODEL}' to available models list")
    AVAILABLE_MODELS.insert(0, DEFAULT_MODEL)

# Log configuration at startup
logger.info(f"TinyChat v{__version__} starting with config:")
logger.info(f"  API URL: {OPENAI_API_URL}")
logger.info(f"  API Key: {'***' + OPENAI_API_KEY[-4:] if OPENAI_API_KEY else 'NOT SET'}")
logger.info(f"  Default Model: {DEFAULT_MODEL}")
logger.info(f"  Available Models: {AVAILABLE_MODELS}")
logger.info(f"  Default Temperature: {DEFAULT_TEMPERATURE}")
logger.info(f"  Security: Max message length {MAX_MESSAGE_LENGTH}")
logger.info(f"  Security: Max conversation history {MAX_CONVERSATION_HISTORY}")
if CHAT_LOG:
    logger.info(f"  Research: Logging conversations to {CHAT_LOG}")
logger.info(f"  Image Generation: Provider={IMAGE_PROVIDER}")
if IMAGE_PROVIDER == "swarmui":
    logger.info(f"  Image Generation: SwarmUI={SWARMUI}, Model={IMAGE_MODEL}")
elif IMAGE_PROVIDER == "openai":
    logger.info(f"  Image Generation: OpenAI Model={OPENAI_IMAGE_MODEL}")

# Security helper functions
def get_client_ip(request: Request) -> str:
    """
    Extract the client's IP address from the request.
    
    Checks X-Forwarded-For header first (for proxied requests), 
    then falls back to direct client host.
    
    Args:
        request: The FastAPI Request object
        
    Returns:
        str: The client's IP address, or "unknown" if unavailable
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else "unknown"

def log_conversation(messages: List[Dict], assistant_response: str, model: str, temperature: float):
    """
    Log conversation thread to JSONL file for research purposes.
    
    Appends a JSON object containing the full conversation history,
    assistant response, model, and temperature to the configured log file.
    Only logs if CHAT_LOG environment variable is set.
    
    Uses an async lock to ensure thread-safe writes when multiple
    conversations are happening concurrently.
    
    Args:
        messages: Full conversation history from the request
        assistant_response: The assistant's complete response
        model: The model used for generation
        temperature: The temperature setting used
    """
    if not CHAT_LOG:
        return
    
    # Schedule the async write operation
    asyncio.create_task(_async_log_conversation(messages, assistant_response, model, temperature))

async def _async_log_conversation(messages: List[Dict], assistant_response: str, model: str, temperature: float):
    """
    Internal async function to perform thread-safe logging.
    
    Uses an asyncio.Lock to ensure only one write happens at a time,
    preventing file corruption from concurrent requests.
    """
    async with _log_lock:
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "temperature": temperature,
                "messages": messages,
                "assistant_response": assistant_response
            }
            
            # Append to JSONL file (one JSON object per line)
            # Use 'a' mode to append, encoding utf-8 for proper character support
            with open(CHAT_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            logger.debug(f"Logged conversation to {CHAT_LOG}")
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

async def generate_image(prompt: str) -> dict:
    """
    Generate an image using SwarmUI or OpenAI and return a data URI.
    
    Args:
        prompt: The text prompt for image generation
        
    Returns:
        dict: A dictionary containing the prompt and image data URI, or error information
    """
    logger.info(f"Image provider: {IMAGE_PROVIDER}")
    
    if IMAGE_PROVIDER == "swarmui":
        logger.info(f"Sending prompt to SwarmUI ({SWARMUI}) model={IMAGE_MODEL}")
        logger.info(f"Prompt: {prompt}")

        async def _get_session_id(session: aiohttp.ClientSession) -> Optional[str]:
            try:
                async with session.post(f"{SWARMUI.rstrip('/')}/API/GetNewSession", json={}, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("session_id")
            except Exception as e:
                logger.error(f"Error getting session id from SwarmUI: {e}")
            return None

        async def _call_generate(session: aiohttp.ClientSession, session_id: str, prompt_text: str) -> Optional[str]:
            params = {
                "model": IMAGE_MODEL,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "cfgscale": IMAGE_CFGSCALE,
                "steps": IMAGE_STEPS,
                "seed": IMAGE_SEED,
            }
            raw_input = {"prompt": str(prompt_text), **{k: v for k, v in params.items()}, "donotsave": True}
            data = {
                "session_id": session_id,
                "images": "1",
                "prompt": str(prompt_text),
                **{k: str(v) for k, v in params.items()},
                "donotsave": True,
                "rawInput": raw_input,
            }
            try:
                async with session.post(f"{SWARMUI.rstrip('/')}/API/GenerateText2Image", json=data, timeout=IMAGE_TIMEOUT) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        imgs = j.get("images") or []
                        if imgs:
                            return imgs[0]
                    else:
                        logger.error(f"SwarmUI GenerateText2Image returned status {resp.status}")
            except Exception as e:
                logger.error(f"Error calling SwarmUI GenerateText2Image: {e}")
            return None

        image_encoded = None
        try:
            async with aiohttp.ClientSession() as session:
                session_id = await _get_session_id(session)
                if not session_id:
                    logger.error("Unable to obtain SwarmUI session id")
                    return {"error": "No session"}
                image_encoded = await _call_generate(session, session_id, prompt)
        except Exception as e:
            logger.error(f"Unexpected error during SwarmUI generation: {e}")
            return {"error": "Generation exception"}

        if not image_encoded:
            logger.error(f"Image generation failed for prompt: {prompt}")
            return {"error": "Generation failed"}
            
    elif IMAGE_PROVIDER == "openai":
        logger.info(f"Sending prompt to OpenAI Images API ({OPENAI_IMAGE_API_BASE}) model={OPENAI_IMAGE_MODEL}")
        logger.info(f"Prompt: {prompt}")

        async def _call_openai(session: aiohttp.ClientSession, prompt_text: str) -> Optional[str]:
            url = f"{OPENAI_IMAGE_API_BASE.rstrip('/')}/images/generations"
            headers = {"Authorization": f"Bearer {OPENAI_IMAGE_API_KEY}", "Content-Type": "application/json"}
            body = {"model": OPENAI_IMAGE_MODEL, "prompt": prompt_text, "size": OPENAI_IMAGE_SIZE}
            try:
                async with session.post(url, json=body, headers=headers, timeout=IMAGE_TIMEOUT) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        data = j.get("data") or []
                        if data:
                            first = data[0]
                            if "b64_json" in first:
                                return first["b64_json"]
                            if "url" in first:
                                # Fetch binary and return as base64
                                img_url = first["url"]
                                async with session.get(img_url) as img_resp:
                                    if img_resp.status == 200:
                                        b = await img_resp.read()
                                        return base64.b64encode(b).decode("utf-8")
                    else:
                        text = await resp.text()
                        logger.error(f"OpenAI images API returned {resp.status}: {text}")
            except Exception as e:
                logger.error(f"Error calling OpenAI Images API: {e}")
            return None

        image_encoded = None
        try:
            async with aiohttp.ClientSession() as session:
                image_encoded = await _call_openai(session, prompt)
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI generation: {e}")
            return {"error": "Generation exception"}

        if not image_encoded:
            logger.error(f"OpenAI image generation failed for prompt: {prompt}")
            return {"error": "Generation failed"}
    else:
        logger.error(f"Unknown IMAGE_PROVIDER: {IMAGE_PROVIDER}")
        return {"error": "Unsupported image provider"}

    # Normalize to raw base64 payload
    if "," in image_encoded:
        image_b64 = image_encoded.split(",", 1)[1]
    else:
        image_b64 = image_encoded

    logger.info(f"Received image data (bytes ~ {len(image_b64)})")

    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_b64)))
    except Exception:
        return {"error": "Unable to decode image data"}

    # Resize down for web if necessary
    max_dim = 1024
    if image.width > max_dim or image.height > max_dim:
        image.thumbnail((max_dim, max_dim))
    # Convert to JPEG for browser-friendliness
    if image.mode == "RGBA":
        image = image.convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    out_b64 = base64.b64encode(out.getvalue()).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{out_b64}"

    return {"prompt": prompt, "image_data": data_uri}

def safe_error_response(message: str, status_code: int = 400):
    """
    Generate error responses that hide internal details in production.
    
    In debug mode, returns the actual error message. In production mode,
    returns generic error messages to avoid leaking implementation details.
    
    Args:
        message: The detailed error message
        status_code: HTTP status code for the response
        
    Returns:
        JSONResponse: A safe error response object
    """
    if ENABLE_DEBUG_LOGS:
        return JSONResponse(
            status_code=status_code,
            content={"error": message, "debug": True}
        )
    else:
        # Generic error messages for production
        generic_messages = {
            400: "Invalid request",
            401: "Unauthorized",
            403: "Forbidden", 
            404: "Not found",
            429: "Too many requests",
            500: "Internal server error"
        }
        return JSONResponse(
            status_code=status_code,
            content={"error": generic_messages.get(status_code, "Request failed")}
        )

app = FastAPI(
    title="TinyChat", 
    description="A minimal chatbot interface",
    docs_url=None if not ENABLE_DEBUG_LOGS else "/docs",  # Hide docs in production
    redoc_url=None if not ENABLE_DEBUG_LOGS else "/redoc"  # Hide redoc in production
)


# Add security middleware
if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Add CORS middleware with restrictions
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Only needed methods
    allow_headers=["*"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware to add security headers to all HTTP responses.
    
    Adds headers for:
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable browser XSS filters
    - Strict-Transport-Security: Enforce HTTPS
    - Content-Security-Policy: Restrict resource loading
    
    Args:
        request: The incoming request
        call_next: The next middleware/handler in the chain
        
    Returns:
        Response with added security headers
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:"
    )
    return response

# Pydantic models with validation
class ChatRequest(BaseModel):
    """
    Request payload for chat streaming endpoint.
    
    In the stateless architecture, the full conversation history is sent
    with each request, allowing the client to manage conversation state.
    
    Attributes:
        messages: Full conversation history as list of message dicts
        temperature: Sampling temperature (0.0-2.0), controls randomness
        model: LLM model to use, must be in AVAILABLE_MODELS
        session_id: Optional session ID for tracking active users
    """
    messages: List[Dict[str, str]] = Field(..., min_items=1, max_items=MAX_CONVERSATION_HISTORY)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    model: Optional[str] = None
    session_id: Optional[str] = None
    
    @validator('model')
    def validate_model(cls, v):
        """Ensure requested model is available."""
        if v is not None and v not in AVAILABLE_MODELS:
            logger.error(f"Invalid model requested: '{v}'. Available models: {', '.join(AVAILABLE_MODELS)}")
            raise ValueError(f"Model must be one of: {', '.join(AVAILABLE_MODELS)}")
        return v
    
    @validator('messages')
    def validate_messages(cls, v):
        """
        Validate message structure and content.
        
        Checks that each message has required fields, valid role,
        and content within length limits.
        """
        for msg in v:
            if 'role' not in msg or 'content' not in msg:
                raise ValueError("Each message must have 'role' and 'content'")
            if msg['role'] not in ['user', 'assistant', 'system']:
                raise ValueError("Role must be 'user', 'assistant', or 'system'")
            if len(msg['content']) > MAX_MESSAGE_LENGTH:
                raise ValueError(f"Message content too long (max {MAX_MESSAGE_LENGTH})")
        return v

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """
    Serve the main chat user interface.
    
    Returns the single-page HTML application that provides the chat interface.
    Handles both development (app/static) and production (static) directory layouts.
    
    Returns:
        HTMLResponse: The rendered HTML page
    """
    html_path = "static/index.html" if os.path.exists("static/index.html") else "app/static/index.html"
    with open(html_path, "r") as f:
        return HTMLResponse(f.read())

async def stream_openai_response(
    messages: List[Dict], 
    temperature: float = DEFAULT_TEMPERATURE,
    model: str = DEFAULT_MODEL
) -> AsyncGenerator[str, None]:
    """
    Stream LLM response chunks from an OpenAI-compatible API.
    
    Makes a streaming POST request to the configured LLM API endpoint
    and yields Server-Sent Events formatted chunks as they arrive.
    
    Args:
        messages: Full conversation history as list of message dicts
                 with 'role' and 'content' keys
        temperature: Sampling temperature (0.0-2.0), controls response randomness
        model: Name of the LLM model to use
        
    Yields:
        str: SSE-formatted data chunks ("data: {json}\n\n")
            containing either content deltas or error messages
            
    Notes:
        - Handles streaming responses line-by-line
        - Logs detailed request/response information for debugging
        - Converts OpenAI SSE format to simplified format
        - Yields error chunks if API request fails
    """
    logger.debug(f"Streaming: {len(messages)} messages → model={model}, temp={temperature}")
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True
    }
    
    # Log the complete request details at DEBUG level
    logger.debug("=" * 80)
    logger.debug(f"🚀 MAKING LLM API REQUEST")
    logger.debug(f"URL: {OPENAI_API_URL}/chat/completions")
    logger.debug(f"Method: POST")
    logger.debug(f"Headers: {json.dumps({k: v if k != 'Authorization' else f'Bearer ***{v[-4:]}' for k, v in headers.items()}, indent=2)}")
    logger.debug(f"Payload:")
    logger.debug(json.dumps(payload, indent=2))
    logger.debug("=" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.debug(f"Making request to {OPENAI_API_URL}/chat/completions")
            
            async with client.stream(
                "POST",
                f"{OPENAI_API_URL}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                logger.debug("=" * 60)
                logger.debug(f"📥 LLM API RESPONSE")
                logger.debug(f"Status: {response.status_code} {response.reason_phrase}")
                logger.debug(f"Headers: {json.dumps(dict(response.headers), indent=2)}")
                logger.debug("=" * 60)
                
                # Handle non-200 responses
                if response.status_code != 200:
                    try:
                        error_content = await response.aread()
                        error_text = error_content.decode('utf-8', errors='ignore')
                    except Exception:
                        error_text = "Could not read error response"
                    
                    logger.error(f"❌ API error {response.status_code}: {error_text}")
                    yield f"data: {json.dumps({'error': error_text})}\n\n"
                    return
                
                line_count = 0
                async for line in response.aiter_lines():
                    line_count += 1
                    logger.debug(f"Received line {line_count}: {line[:100]}...")
                    
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            logger.debug("Stream completed with [DONE]")
                            break
                        
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and chunk["choices"]:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    content = delta["content"]
                                    logger.debug(f"Yielding content: {repr(content)}")
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON chunk: {data} - Error: {e}")
                            continue
                
                logger.debug(f"Stream completed: {line_count} lines received")
                            
    except httpx.HTTPStatusError as e:
        # Read the response content properly for streaming responses
        try:
            if hasattr(e.response, 'aread'):
                error_content = await e.response.aread()
                error_text = error_content.decode('utf-8', errors='ignore')
            else:
                error_text = str(e.response.content) if e.response.content else "No response content"
        except Exception:
            error_text = "Could not read error response"
            
        error_msg = f"HTTP error {e.response.status_code}: {error_text}"
        logger.error(error_msg)
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'error': error_msg})}\n\n"

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    """
    Stream chat completions via Server-Sent Events (stateless endpoint).
    
    This is the main chat endpoint. It receives the full conversation history
    from the client, forwards it to the LLM API, and streams the response back.
    The server is stateless - all conversation state is managed client-side.
    
    Args:
        request: ChatRequest with messages array, optional temperature and model
        http_request: The HTTP request context for logging
        
    Returns:
        StreamingResponse: SSE stream of response chunks
        
    Raises:
        HTTPException: 500 if API key is not configured
        
    Notes:
        - Client sends full conversation history with each request
        - Server validates input but doesn't store conversations
        - Response is streamed token-by-token for real-time display
        - Errors are yielded as SSE events to maintain stream integrity
    """
    client_ip = get_client_ip(http_request)
    
    # Determine which model will be used
    model_to_use = request.model or DEFAULT_MODEL
    temp_to_use = request.temperature or DEFAULT_TEMPERATURE
    
    logger.debug(f"Chat stream request from {client_ip}: {len(request.messages)} messages")
    logger.debug(f"  Model: {model_to_use} (requested: {request.model or 'default'})")
    logger.debug(f"  Temperature: {temp_to_use}")
    
    # Validate API key
    if not OPENAI_API_KEY:
        logger.error("API key not configured")
        raise HTTPException(status_code=500, detail="Service configuration error")
    
    # Update session timestamp if provided
    if request.session_id:
        async with _page_loads_lock:
            _page_loads[request.session_id] = datetime.now()
    
    # Check if this is an image generation request
    last_message = request.messages[-1] if request.messages else None
    if last_message and last_message.get('role') == 'user':
        user_content = last_message.get('content', '').strip()
        if user_content.startswith('/image '):
            # Extract the image prompt
            image_prompt = user_content[7:].strip()  # Remove '/image ' prefix
            
            if not image_prompt:
                async def error_gen():
                    yield f"data: {json.dumps({'content': 'Please provide a prompt for the image. Usage: /image <prompt>'})}\n\n"
                return StreamingResponse(error_gen(), media_type="text/plain", headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream"
                })
            
            # Generate image
            async def image_gen():
                global _active_generations
                async with _generations_lock:
                    _active_generations += 1
                
                try:
                    logger.info(f"Image generation request from {client_ip}: {image_prompt}")
                    
                    # Send initial message
                    yield f"data: {json.dumps({'content': 'Generating image...'})}\n\n"
                    
                    # Generate the image
                    result = await generate_image(image_prompt)
                    
                    if "error" in result:
                        error_msg = f"Error generating image: {result['error']}"
                        yield f"data: {json.dumps({'content': error_msg})}\n\n"
                    else:
                        # Send the image data
                        response_data = {'image': result['image_data'], 'content': 'Here is your image.'}
                        yield f"data: {json.dumps(response_data)}\n\n"
                        
                        # Log conversation with text only (not full image data)
                        log_conversation(request.messages, f"[Generated image: {image_prompt}]", "image-gen", 0.0)
                except Exception as e:
                    logger.error(f"Error in image generation: {e}\n{traceback.format_exc()}")
                    yield f"data: {json.dumps({'content': 'Failed to generate image.'})}\n\n"
                finally:
                    async with _generations_lock:
                        _active_generations -= 1
            
            return StreamingResponse(image_gen(), media_type="text/plain", headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            })
    
    # Use provided messages directly (client manages conversation history)
    api_messages = request.messages
    
    async def generate():
        global _active_generations
        
        # Increment active generations counter
        async with _generations_lock:
            _active_generations += 1
        
        try:
            logger.debug("Starting response generation")
            
            assistant_content = ""
            chunk_count = 0
            
            try:
                async for chunk in stream_openai_response(
                    api_messages,
                    temp_to_use,
                    model_to_use
                ):
                    chunk_count += 1
                    logger.debug(f"Yielding chunk {chunk_count}: {chunk[:50]}...")
                    yield chunk
                    
                    # Extract content for logging
                    try:
                        data = json.loads(chunk[6:])  # Remove "data: " prefix
                        if "content" in data:
                            assistant_content += data["content"]
                    except Exception as e:
                        logger.debug(f"Failed to extract content from chunk: {e}")
                        pass
                
                if assistant_content:
                    logger.debug(f"Response completed: {len(assistant_content)} chars, {chunk_count} chunks")
                    
                    # Log conversation for research purposes if enabled
                    log_conversation(api_messages, assistant_content, model_to_use, temp_to_use)
                else:
                    logger.warning("No assistant content received")

            except Exception as e:
                error_msg = f"Error during generation: {str(e)}"
                if ENABLE_DEBUG_LOGS:
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                else:
                    logger.error("Generation error")
                yield f"data: {json.dumps({'error': 'Generation failed'})}\n\n"
        
        finally:
            # Decrement active generations counter
            async with _generations_lock:
                _active_generations -= 1
    
    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.get("/api/config")
async def get_config(http_request: Request):
    """
    Provide client configuration settings.
    
    Returns dynamic configuration that the frontend needs to operate,
    including available models, defaults, and security limits.
    
    Returns:
        dict: Configuration object with:
            - available_models: List of model names client can select
            - default_model: Default model to pre-select
            - default_temperature: Default temperature value
            - api_configured: Whether API key is set up
            - max_message_length: Maximum characters per message
            - max_conversation_history: Maximum messages per conversation
            - version: Application version
    """
    return {
        "available_models": AVAILABLE_MODELS,
        "default_model": DEFAULT_MODEL,
        "default_temperature": DEFAULT_TEMPERATURE,
        "api_configured": bool(OPENAI_API_KEY),
        "max_message_length": MAX_MESSAGE_LENGTH,
        "max_conversation_history": MAX_CONVERSATION_HISTORY,
        "version": __version__
    }

@app.get("/api/version")
async def get_version():
    """
    Get application version.
    
    Returns:
        dict: Version information
    """
    return {"version": __version__}

@app.get("/api/session")
async def create_session(session_id: Optional[str] = None):
    """
    Create or update a session when page loads.
    
    Args:
        session_id: Optional existing session ID to refresh
    
    Returns:
        dict: Session ID for tracking
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    async with _page_loads_lock:
        _page_loads[session_id] = datetime.now()
    
    return {"session_id": session_id}


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns basic service health status, active sessions, and concurrent generations.
    
    Returns:
        dict: Health status with:
            - status: Service status ("healthy")
            - timestamp: Current timestamp
            - active_sessions: Number of sessions (page loads) in last 5 minutes
            - active_generations: Number of concurrent streaming generations
    """
    # Clean up expired sessions and count active ones
    now = datetime.now()
    cutoff = now - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    
    async with _page_loads_lock:
        # Remove expired sessions
        expired_sessions = [sid for sid, ts in _page_loads.items() if ts < cutoff]
        for sid in expired_sessions:
            del _page_loads[sid]
        
        active_session_count = len(_page_loads)
    
    return {
        "status": "healthy", 
        "timestamp": now,
        "active_sessions": active_session_count,
        "active_generations": _active_generations
    }

# Mount static files
import os
static_dir = "static" if os.path.exists("static") else "app/static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )