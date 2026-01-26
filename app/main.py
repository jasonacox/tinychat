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

import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from app.config import Settings
from app.middleware.security import setup_security_middleware, add_security_headers
from app.utils.error_handlers import validation_exception_handler
from app.api.v1.root import router as root_router
from app.api.v1.chat import router as chat_router
from app.api.v1.config import router as config_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tinychat")

# Create FastAPI app
app = FastAPI(
    title="TinyChat",
    description="A minimal chatbot interface",
    docs_url=None if not Settings.ENABLE_DEBUG_LOGS else "/docs",
    redoc_url=None if not Settings.ENABLE_DEBUG_LOGS else "/redoc"
)

# Setup security middleware
setup_security_middleware(app)

# Add security headers middleware
@app.middleware("http")
async def security_headers_middleware(request, call_next):
    return await add_security_headers(request, call_next)

# Add error handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(root_router)
app.include_router(chat_router)
app.include_router(config_router)

# Mount static files
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
