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
    def filter_images_keep_latest(messages: List[Dict]) -> List[Dict]:
        """
        Remove all images except the most recent one.
        
        This prevents API errors with LLMs that only support single images.
        Keeps the last user message with an image, removes all prior images.
        
        Args:
            messages: Full conversation history
            
        Returns:
            Filtered messages with only the most recent image
        """
        # Find index of last message with image
        last_image_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get('image'):
                last_image_idx = i
                break
        
        # If no images found, return as-is
        if last_image_idx is None:
            return messages
        
        # Remove all images except the last one
        filtered = []
        for i, msg in enumerate(messages):
            msg_copy = msg.copy()
            if msg_copy.get('image') and i != last_image_idx:
                # Remove image from this message
                msg_copy.pop('image', None)
                msg_copy.pop('image_type', None)
            filtered.append(msg_copy)
        
        logger.debug(f"Filtered images: kept image at index {last_image_idx}, removed {sum(1 for m in messages if m.get('image')) - 1} older images")
        return filtered
    
    @staticmethod
    def format_message_for_vision_api(message: Dict) -> Dict:
        """
        Format message with image for OpenAI-compatible vision APIs.
        
        OpenAI vision format:
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ]
        }
        
        This format works with:
        - OpenAI GPT-4 Vision models
        - Any OpenAI-compatible API that supports vision (LM Studio, Ollama, etc.)
        
        Args:
            message: Message dict with optional 'image' and 'image_type' fields
            
        Returns:
            Formatted message dict for API
        """
        if not message.get('image'):
            # No image, return as plain text message
            return {"role": message["role"], "content": message["content"]}
        
        # Format with image using OpenAI's content array format
        return {
            "role": message["role"],
            "content": [
                {"type": "text", "text": message["content"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{message['image_type']};base64,{message['image']}"
                    }
                }
            ]
        }
    
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
        Handles image attachments for vision-capable models.
        
        Args:
            messages: Full conversation history as list of message dicts
                     with 'role' and 'content' keys. May include optional
                     'image' and 'image_type' fields for vision requests.
            temperature: Sampling temperature (0.0-2.0), controls response randomness
            model: Name of the LLM model to use
            
        Yields:
            str: SSE-formatted data chunks ("data: {json}\n\n")
                containing either content deltas or error messages
                
        Notes:
            - Handles streaming responses line-by-line
            - Logs detailed request/response information for debugging
            - Converts OpenAI SSE format to simplified format
            - Automatically filters to keep only the most recent image
            - Formats messages for vision API when images are present
            - Yields error chunks if API request fails
        """
        temperature = temperature or Settings.DEFAULT_TEMPERATURE
        model = model or Settings.DEFAULT_MODEL
        
        logger.debug(f"Streaming: {len(messages)} messages → model={model}, temp={temperature}")
        
        # Filter images (keep only the most recent one)
        messages = LLMService.filter_images_keep_latest(messages)
        
        # Always format messages for vision API - assume all models support vision
        # If they don't, we'll catch the error and handle it gracefully
        formatted_messages = [
            LLMService.format_message_for_vision_api(msg) 
            for msg in messages
        ]
        
        headers = {
            "Authorization": f"Bearer {Settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True
        }
        
        # Log the complete request details at DEBUG level
        logger.debug("=" * 80)
        logger.debug(f"🚀 MAKING LLM API REQUEST")
        logger.debug(f"URL: {Settings.OPENAI_API_URL}/chat/completions")
        logger.debug(f"Method: POST")
        logger.debug(f"Headers: {json.dumps({k: v if k != 'Authorization' else f'Bearer ***{v[-4:]}' for k, v in headers.items()}, indent=2)}")
        
        # Log payload but truncate base64 image data for readability
        debug_payload = json.loads(json.dumps(payload))
        for msg in debug_payload.get('messages', []):
            if isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if item.get('type') == 'image_url' and 'image_url' in item:
                        url = item['image_url'].get('url', '')
                        if len(url) > 100:
                            item['image_url']['url'] = url[:100] + f"... ({len(url)} chars)"
        
        logger.debug(f"Payload:")
        logger.debug(json.dumps(debug_payload, indent=2))
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
                        
                        # Check for vision-related errors
                        error_lower = error_text.lower()
                        if any(keyword in error_lower for keyword in [
                            'image', 'vision', 'multimodal', 'content type', 'invalid content',
                            'content array', 'image_url', 'image_data', 'should be a valid string', 'input should be'
                        ]):
                            vision_error_msg = "The language model was unable to process your image. Removing."
                            logger.warning(f"Model doesn't support vision (HTTP {response.status_code}): {error_text}")
                            yield f"data: {json.dumps({'error': 'vision_not_supported', 'message': vision_error_msg, 'remove_images': True})}\n\n"
                            return
                        
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
            
            # Check for vision-related errors
            error_lower = error_text.lower()
            if any(keyword in error_lower for keyword in [
                'image', 'vision', 'multimodal', 'content type', 'invalid content',
                'content array', 'image_url', 'image_data', 'should be a valid string'
            ]):
                vision_error_msg = "This model does not support image inputs. The image has been removed from the conversation."
                logger.warning(f"Model doesn't support vision: {error_text}")
                yield f"data: {json.dumps({'error': 'vision_not_supported', 'message': vision_error_msg, 'remove_images': True})}\n\n"
                return
            
            error_msg = f"HTTP error {e.response.status_code}: {error_text}"
            logger.error(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        except Exception as e:
            # Check if it's a vision-related exception
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in [
                'image', 'vision', 'multimodal', 'content type', 'invalid content', 'should be a valid string'
            ]):
                vision_error_msg = "This model does not support image inputs. The image has been removed from the conversation."
                logger.warning(f"Model doesn't support vision: {str(e)}")
                yield f"data: {json.dumps({'error': 'vision_not_supported', 'message': vision_error_msg, 'remove_images': True})}\n\n"
                return
            
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
