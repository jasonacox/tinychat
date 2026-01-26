"""LLM service for handling OpenAI-compatible API interactions."""

import json
import logging
import traceback
from typing import Dict, List, AsyncGenerator

import httpx

from app.config import Settings

logger = logging.getLogger("tinychat")


class LLMService:
    """Service for interacting with LLM APIs."""
    
    @staticmethod
    async def stream_completion(
        messages: List[Dict], 
        temperature: float = None,
        model: str = None
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
        temperature = temperature or Settings.DEFAULT_TEMPERATURE
        model = model or Settings.DEFAULT_MODEL
        
        logger.debug(f"Streaming: {len(messages)} messages → model={model}, temp={temperature}")
        
        headers = {
            "Authorization": f"Bearer {Settings.OPENAI_API_KEY}",
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
        logger.debug(f"URL: {Settings.OPENAI_API_URL}/chat/completions")
        logger.debug(f"Method: POST")
        logger.debug(f"Headers: {json.dumps({k: v if k != 'Authorization' else f'Bearer ***{v[-4:]}' for k, v in headers.items()}, indent=2)}")
        logger.debug(f"Payload:")
        logger.debug(json.dumps(payload, indent=2))
        logger.debug("=" * 80)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Making request to {Settings.OPENAI_API_URL}/chat/completions")
                
                async with client.stream(
                    "POST",
                    f"{Settings.OPENAI_API_URL}/chat/completions",
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
