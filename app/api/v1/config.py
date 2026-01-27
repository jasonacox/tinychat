"""Configuration and system endpoints."""

import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request

from app.api.schemas import RLMPasscodeRequest
from app.config import Settings
from app.utils.security import get_client_ip
from app.utils.state import StateManager

logger = logging.getLogger("tinychat")

router = APIRouter()


@router.get("/api/config")
async def get_config():
    """
    Get client configuration including available models and default settings.
    
    This endpoint provides the frontend with the configuration needed to
    initialize the chat interface, including:
    - List of available LLM models
    - Default model and temperature
    - Whether RLM is available
    - Maximum conversation history length
    
    Returns:
        dict: Configuration object with models, defaults, and feature flags
    """
    return {
        "available_models": Settings.AVAILABLE_MODELS,
        "default_model": Settings.DEFAULT_MODEL,
        "default_temperature": Settings.DEFAULT_TEMPERATURE,
        "has_rlm": Settings.HAS_RLM,
        "max_conversation_history": Settings.MAX_CONVERSATION_HISTORY,
        "max_images_in_context": Settings.MAX_IMAGES_IN_CONTEXT,
        "max_document_size_mb": Settings.MAX_DOCUMENT_SIZE_MB,
        "max_documents_in_context": Settings.MAX_DOCUMENTS_IN_CONTEXT,
        "supported_document_types": Settings.SUPPORTED_DOCUMENT_TYPES,
        "version": Settings.VERSION,
    }


@router.get("/api/version")
async def get_version():
    """
    Get the TinyChat version.
    
    Returns:
        dict: Version information
    """
    return {"version": Settings.VERSION}


@router.post("/api/rlm/validate")
async def validate_rlm_passcode(request: RLMPasscodeRequest, http_request: Request):
    """
    Validate the RLM passcode.
    
    This endpoint checks if the provided passcode matches the configured
    RLM_PASSCODE. Used by the frontend to verify access before enabling
    the RLM toggle.
    
    Args:
        request: Request containing the passcode to validate
        http_request: HTTP request for logging
    
    Returns:
        dict: Validation result with 'valid' boolean
    """
    client_ip = get_client_ip(http_request)
    
    if not Settings.RLM_PASSCODE:
        logger.warning(f"RLM passcode validation attempted but RLM_PASSCODE not configured (from {client_ip})")
        return {"error": "RLM passcode not configured on server"}
    
    if request.passcode == Settings.RLM_PASSCODE:
        logger.info(f"✓ Valid RLM passcode from {client_ip}")
        return {"valid": True}
    else:
        logger.warning(f"❌ Invalid RLM passcode attempt from {client_ip}")
        return {"valid": False}


@router.get("/api/rlm/status")
async def get_rlm_status():
    """
    Check if RLM is available and whether it requires a passcode.
    
    This endpoint is called by the frontend on startup to determine
    whether to show the RLM toggle and whether to prompt for a passcode.
    
    Returns:
        dict: RLM status with:
            - available: Whether RLM package is installed
            - requires_passcode: Whether RLM_PASSCODE is configured
    """
    return {
        "available": Settings.HAS_RLM,
        "requires_passcode": bool(Settings.RLM_PASSCODE)
    }


@router.get("/api/session")
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
    
    await StateManager.track_session(session_id)
    active_count = await StateManager.get_active_sessions()
    
    return {
        "session_id": session_id,
        "active_sessions": active_count
    }


@router.get("/api/health")
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
    active_sessions = await StateManager.get_active_sessions()
    active_gens = await StateManager.get_active_generations()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "active_sessions": active_sessions,
        "active_generations": active_gens
    }
