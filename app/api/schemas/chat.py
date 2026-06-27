"""Pydantic models for chat endpoints."""

import logging
import re
from typing import Any, Dict, List, Optional
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
    messages: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=Settings.MAX_CONVERSATION_HISTORY
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    model: Optional[str] = None
    backend: Optional[str] = None
    session_id: Optional[str] = None
    rlm: Optional[bool] = False
    rlm_passcode: Optional[str] = None
    show_rlm_thinking: Optional[bool] = True

    @field_validator('model')
    @classmethod
    def validate_model(cls, v):
        """
        Validate model name.

        Always enforces a max length and safe character set to prevent
        oversized or specially crafted strings from reaching upstream APIs.

        In single-backend mode, also validates against AVAILABLE_MODELS.
        In multi-backend mode, strict list-membership is skipped (backends
        like Ollama accept unlisted models); the endpoint handler does a
        soft warning check instead.
        """
        if v is None:
            return v

        # Always enforce max length and safe character set regardless of mode
        if len(v) > 200:
            raise ValueError("Model name too long (max 200 characters)")
        if not re.match(r'^[a-zA-Z0-9._:/@-]+$', v):
            raise ValueError(
                "Model name contains invalid characters. "
                "Allowed: letters, digits, and . _ : / @ -"
            )

        if len(Settings.API_BACKENDS) <= 1:
            # Single-backend mode: strict validation against known models
            if v not in Settings.AVAILABLE_MODELS:
                logger.error(f"Invalid model requested: '{v}'. Available models: {', '.join(Settings.AVAILABLE_MODELS)}")
                raise ValueError(f"Model must be one of: {', '.join(Settings.AVAILABLE_MODELS)}")
        return v
    
    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """
        Validate message structure and content.

        Checks that each message has required fields, valid role,
        and content within length limits. Also validates optional image fields.

        Content may be a string (plain text) or an array of content parts
        (OpenAI multimodal format for vision), e.g.:
        [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:..."}}]
        """
        for msg in v:
            if 'role' not in msg or 'content' not in msg:
                raise ValueError("Each message must have 'role' and 'content'")
            if msg['role'] not in ['user', 'assistant', 'system']:
                raise ValueError("Role must be 'user', 'assistant', or 'system'")

            content = msg['content']

            # Content can be a string or an array (OpenAI multimodal format)
            if isinstance(content, str):
                if len(content) > Settings.MAX_MESSAGE_LENGTH:
                    raise ValueError(f"Message content too long (max {Settings.MAX_MESSAGE_LENGTH})")
            elif isinstance(content, list):
                # Validate multimodal content array
                for part in content:
                    if not isinstance(part, dict) or 'type' not in part:
                        raise ValueError("Each content part must have a 'type' field")
                    if part['type'] == 'text':
                        if 'text' not in part:
                            raise ValueError("Text content part must have a 'text' field")
                        if not isinstance(part['text'], str):
                            raise ValueError("Text content part 'text' must be a string")
                        if len(part['text']) > Settings.MAX_MESSAGE_LENGTH:
                            raise ValueError(f"Text content too long (max {Settings.MAX_MESSAGE_LENGTH})")
                    elif part['type'] == 'image_url':
                        if not isinstance(part.get('image_url'), dict):
                            raise ValueError("image_url content part must have an 'image_url' object")
                        url = part['image_url'].get('url')
                        if not isinstance(url, str):
                            raise ValueError("image_url.url must be a string")
                        # Accept data URIs (base64 images) and remote URLs
                        if not (url.startswith('data:image/') or url.startswith('http://') or url.startswith('https://')):
                            raise ValueError("image_url must be a data URI or HTTP(S) URL")
                        # Enforce size limit on data URIs to prevent unbounded payloads
                        if url.startswith('data:'):
                            estimated_size = len(url) * 3 / 4  # approximate decoded size
                            max_image_size = 10 * 1024 * 1024  # 10MB, consistent with legacy image field
                            if estimated_size > max_image_size:
                                raise ValueError(f"Image in content array too large (max 10MB)")
                    else:
                        raise ValueError(f"Unknown content part type: {part['type']}")
            else:
                raise ValueError("Message content must be a string or array of content parts")
            
            # Validate optional image fields
            if 'image' in msg:
                # Validate image is base64 string (basic check)
                image_data = msg['image']
                if not isinstance(image_data, str) or len(image_data) == 0:
                    raise ValueError("Image data must be a non-empty string")
                
                # Check for valid base64 characters (basic validation)
                if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', image_data):
                    raise ValueError("Image data must be valid base64")
                
                # Validate image_type if image is present
                if 'image_type' not in msg:
                    raise ValueError("image_type is required when image is provided")
                
                valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if msg['image_type'] not in valid_types:
                    raise ValueError(f"image_type must be one of: {', '.join(valid_types)}")
                
                # Estimate size (base64 is ~1.33x original size)
                estimated_size = (len(image_data) * 3) / 4
                max_size = 10 * 1024 * 1024  # 10MB
                if estimated_size > max_size:
                    raise ValueError(f"Image too large (max 10MB)")
            
            # Validate optional document fields
            if 'document' in msg:
                doc = msg['document']
                if not isinstance(doc, dict):
                    raise ValueError("Document must be an object")
                
                # Check required document fields
                required_fields = ['name', 'type', 'size', 'pages', 'markdown']
                for field in required_fields:
                    if field not in doc:
                        raise ValueError(f"Document missing required field: {field}")
                
                # Validate document type
                if doc['type'] not in Settings.SUPPORTED_DOCUMENT_TYPES:
                    raise ValueError(f"Unsupported document type: {doc['type']}")
                
                # Validate document size
                max_doc_size = Settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
                if doc['size'] > max_doc_size:
                    raise ValueError(f"Document too large (max {Settings.MAX_DOCUMENT_SIZE_MB}MB)")
        
        return v
