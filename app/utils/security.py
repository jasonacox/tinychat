"""Security utility functions."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import Settings


def get_client_ip(request: Request) -> str:
    """
    Extract the client's IP address from the request.
    
    Checks X-Forwarded-For header first (for proxied requests),
    then X-Real-IP, then falls back to direct client host.
    
    Args:
        request: The FastAPI Request object
        
    Returns:
        str: The client's IP address, or "unknown" if unavailable
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    return request.client.host if request.client else "unknown"


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
    if Settings.ENABLE_DEBUG_LOGS:
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
