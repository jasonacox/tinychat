"""Logging service for conversation tracking."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List

from app.config import Settings

logger = logging.getLogger("tinychat")

# File lock for thread-safe logging
_log_lock = asyncio.Lock()


class LoggingService:
    """Service for logging conversations to file."""
    
    @staticmethod
    def log_conversation(
        messages: List[Dict], 
        assistant_response: str, 
        model: str, 
        temperature: float
    ):
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
        if not Settings.CHAT_LOG:
            return
        
        # Schedule the async write operation
        asyncio.create_task(
            LoggingService._async_log_conversation(
                messages, assistant_response, model, temperature
            )
        )
    
    @staticmethod
    async def _async_log_conversation(
        messages: List[Dict], 
        assistant_response: str, 
        model: str, 
        temperature: float
    ):
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
                with open(Settings.CHAT_LOG, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
                logger.debug(f"Logged conversation to {Settings.CHAT_LOG}")
            except Exception as e:
                logger.error(f"Failed to log conversation: {e}")
