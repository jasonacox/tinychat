"""Pydantic models for chat endpoints."""

import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.config import Settings

logger = logging.getLogger("tinychat")


class RLMPasscodeRequest(BaseModel):
    """
    Request payload for RLM passcode validation.
    
    Attributes:
        passcode: The passcode to validate
    """
    passcode: str = Field(..., min_length=1, max_length=100)


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
        rlm: Whether to use RLM (requires passcode if RLM_PASSCODE is set)
        rlm_passcode: Passcode for RLM access (required if RLM_PASSCODE is configured)
        show_rlm_thinking: Whether to stream RLM thinking process
    """
    messages: List[Dict[str, str]] = Field(
        ..., 
        min_length=1, 
        max_length=Settings.MAX_CONVERSATION_HISTORY
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    model: Optional[str] = None
    session_id: Optional[str] = None
    rlm: Optional[bool] = False
    rlm_passcode: Optional[str] = None
    show_rlm_thinking: Optional[bool] = True
    
    @field_validator('model')
    @classmethod
    def validate_model(cls, v):
        """Ensure requested model is available."""
        if v is not None and v not in Settings.AVAILABLE_MODELS:
            logger.error(f"Invalid model requested: '{v}'. Available models: {', '.join(Settings.AVAILABLE_MODELS)}")
            raise ValueError(f"Model must be one of: {', '.join(Settings.AVAILABLE_MODELS)}")
        return v
    
    @field_validator('messages')
    @classmethod
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
            if len(msg['content']) > Settings.MAX_MESSAGE_LENGTH:
                raise ValueError(f"Message content too long (max {Settings.MAX_MESSAGE_LENGTH})")
        return v
