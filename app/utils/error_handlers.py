"""Error handler utilities."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import Settings

logger = logging.getLogger("tinychat")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Convert Pydantic request validation errors into clearer JSON messages
    (e.g., when a message exceeds MAX_MESSAGE_LENGTH).
    """
    errors = exc.errors()
    # Look for specific message-too-long validation and return a friendly error
    for err in errors:
        msg = err.get("msg", "")
        loc = err.get("loc", [])
        if "Message content too long" in msg:
            detail = msg
            return JSONResponse(status_code=422, content={
                "error": "MessageTooLong",
                "detail": detail,
                "max_message_length": Settings.MAX_MESSAGE_LENGTH,
                "location": loc,
            })
    
    # Fallback: return summarized validation errors
    simplified = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in errors]
    return JSONResponse(
        status_code=422, 
        content={"error": "ValidationError", "detail": simplified}
    )
