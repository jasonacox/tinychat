"""LLM service for handling OpenAI-compatible API interactions."""

import json
import logging
import traceback
import time
from typing import Dict, List, AsyncGenerator, Optional, Tuple

import httpx

from app.config import Settings

logger = logging.getLogger("tinychat")

# Health check cache (timestamp, result) - cached for 5 seconds
_llm_health_cache: Optional[Tuple[float, bool]] = None


class LLMService:
    """Service for interacting with LLM APIs."""
    
    @staticmethod
    async def check_health() -> bool:
        """
        Check connectivity to the LLM backend.
        Results are cached for 5 seconds to prevent DDoS.
        
        Returns:
            bool: True if LLM backend is reachable and responding, False otherwise
        """
        global _llm_health_cache
        
        # Check cache
        if _llm_health_cache is not None:
            cache_time, cached_result = _llm_health_cache
            if time.time() - cache_time < 5.0:
                return cached_result
        
        # Perform health check
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{Settings.OPENAI_API_URL.rstrip('/')}/models",
                    headers={
                        "Authorization": f"Bearer {Settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    }
                )
                result = response.status_code == 200
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            result = False
        
        # Update cache
        _llm_health_cache = (time.time(), result)
        return result
    
    @staticmethod
    def inject_document_context(messages: List[Dict], max_documents: int = None) -> List[Dict]:
        """
        Inject document context into system message for non-RLM sessions.
        
        Finds the most recent N documents and prepends them to the conversation
        as a system message.
        
        Args:
            messages: Conversation history
            max_documents: Maximum number of documents to include (defaults to MAX_DOCUMENTS_IN_CONTEXT)
            
        Returns:
            Modified messages with document context injected
        """
        if max_documents is None:
            max_documents = Settings.MAX_DOCUMENTS_IN_CONTEXT
        
        # Find recent documents
        documents = []
        for msg in reversed(messages):
            if msg.get("document") and len(documents) < max_documents:
                doc = msg["document"]
                documents.insert(0, {
                    "name": doc["name"],
                    "content": doc["markdown"]
                })
        
        if not documents:
            return messages
        
        # Check if there are images in the conversation
        has_images = any(msg.get('image') for msg in messages)
        
        # Build context string
        context_parts = []
        for doc in documents:
            context_parts.append(f"# Document: {doc['name']}\n\n{doc['content']}")
        
        # Make the instruction more prominent if there are also images
        if has_images:
            instruction = """IMPORTANT: The following documents have been provided as context. When answering questions, you must consider BOTH the document content below AND any images in the conversation. Give equal weight to both sources of information.

Documents:

{documents}

---

Base your answers on both the document content above and any images provided in the conversation."""
        else:
            instruction = """The following documents have been provided as context. Use them to answer the user's questions:

{documents}

---

Answer the user's questions based on the above context."""
        
        context_message = {
            "role": "system",
            "content": instruction.format(documents=chr(10).join(context_parts))
        }
        
        # Insert at beginning (after any existing system messages)
        modified = messages.copy()
        system_idx = 0
        for i, msg in enumerate(modified):
            if msg["role"] == "system":
                system_idx = i + 1
            else:
                break
        
        modified.insert(system_idx, context_message)
        logger.debug(f"Injected {len(documents)} document(s) into conversation context at index {system_idx}")
        logger.debug(f"Document context preview: {context_message['content'][:200]}...")
        return modified
    
    @staticmethod
    def _has_image(msg: Dict) -> bool:
        """Check if a message contains an image (legacy field or multimodal array)."""
        if msg.get('image'):
            return True
        content = msg.get('content')
        if isinstance(content, list):
            return any(
                isinstance(p, dict) and p.get('type') == 'image_url'
                for p in content
            )
        return False

    @staticmethod
    def filter_images_keep_latest(messages: List[Dict]) -> List[Dict]:
        """
        Remove all images except the most recent one.
        
        This prevents API errors with LLMs that only support single images.
        Keeps the last user message with an image, removes all prior images.
        Handles both legacy 'image' field and multimodal 'content' arrays.
        
        Args:
            messages: Full conversation history
            
        Returns:
            Filtered messages with only the most recent image
        """
        # Find index of last message with image (legacy or multimodal)
        last_image_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if LLMService._has_image(messages[i]):
                last_image_idx = i
                break
        
        # If no images found, return as-is
        if last_image_idx is None:
            return messages
        
        # Remove all images except the last one
        filtered = []
        for i, msg in enumerate(messages):
            if i == last_image_idx:
                filtered.append(msg)
                continue

            msg_copy = msg.copy()
            if msg_copy.get('image'):
                # Remove legacy image fields
                msg_copy.pop('image', None)
                msg_copy.pop('image_type', None)

            content = msg_copy.get('content')
            if isinstance(content, list):
                # Remove image_url parts from multimodal content arrays
                msg_copy['content'] = [
                    p for p in content
                    if not (isinstance(p, dict) and p.get('type') == 'image_url')
                ]
                # If only text parts remain, collapse back to string for efficiency
                if len(msg_copy['content']) == 1 and msg_copy['content'][0].get('type') == 'text':
                    msg_copy['content'] = msg_copy['content'][0].get('text', '')
                elif len(msg_copy['content']) == 0:
                    msg_copy['content'] = ''

            filtered.append(msg_copy)
        
        logger.debug(f"Filtered images: kept image at index {last_image_idx}, removed older images")
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

        Handles three cases:
        1. Content is already a multimodal array (pass through as-is)
        2. Message has separate 'image' field (convert to array format)
        3. Plain text message (return string content)

        Args:
            message: Message dict with optional 'image' and 'image_type' fields.
                     Content may be a string or already a multimodal array.

        Returns:
            Formatted message dict for API
        """
        content = message.get("content", "")

        # If content is already a multimodal array, pass through
        if isinstance(content, list):
            return {"role": message["role"], "content": content}

        if not message.get('image'):
            # No image, return as plain text message
            return {"role": message["role"], "content": content}

        # Format with image using OpenAI's content array format
        return {
            "role": message["role"],
            "content": [
                {"type": "text", "text": content},
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
        model: str = None,
        api_url: str = None,
        api_key: str = None,
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
            api_url: Override API base URL (for multi-backend support)
            api_key: Override API key (for multi-backend support)

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
        api_url = api_url or Settings.OPENAI_API_URL
        api_key = api_key or Settings.OPENAI_API_KEY
        
        logger.debug(f"Streaming: {len(messages)} messages → model={model}, temp={temperature}")
        
        # Check for images and documents in the conversation
        has_images = any(msg.get('image') for msg in messages)
        has_documents = any(msg.get('document') for msg in messages)
        if has_images and has_documents:
            logger.warning(f"⚠️  Conversation has both images AND documents - both should be in context")
        elif has_images:
            logger.debug(f"📷 Conversation includes images")
        elif has_documents:
            logger.debug(f"📄 Conversation includes documents")
        
        # Filter images (keep only the most recent one)
        messages = LLMService.filter_images_keep_latest(messages)
        
        # Always format messages for vision API - assume all models support vision
        # If they don't, we'll catch the error and handle it gracefully
        formatted_messages = [
            LLMService.format_message_for_vision_api(msg) 
            for msg in messages
        ]
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        
        # Log the complete request details at DEBUG level
        logger.debug("=" * 80)
        logger.debug(f"🚀 MAKING LLM API REQUEST")
        logger.debug(f"URL: {api_url}/chat/completions")
        logger.debug(f"Method: POST")
        logger.debug(f"Headers: {json.dumps({k: (v if k != 'Authorization' else ('Bearer ***' + v[-4:] if len(v) > 10 else 'Bearer ***')) for k, v in headers.items()}, indent=2)}")
        
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
            # Attempt up to 2 times: first with stream_options (for token usage),
            # then without if the backend rejects it (e.g. Ollama, older LiteLLM).
            for attempt in range(2):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.debug(f"Making request to {api_url}/chat/completions (attempt {attempt + 1})")

                    async with client.stream(
                        "POST",
                        f"{api_url}/chat/completions",
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

                            # On first attempt, check if the backend rejected stream_options.
                            # Common indicators: "unknown field", "extra inputs", "stream_options".
                            if attempt == 0 and response.status_code in (400, 422):
                                error_lower = error_text.lower()
                                if any(kw in error_lower for kw in [
                                    'stream_options', 'unknown field', 'extra inputs',
                                    'unexpected keyword', 'unrecognized'
                                ]):
                                    logger.warning(
                                        f"⚠️  Backend '{api_url}' rejected stream_options "
                                        f"(HTTP {response.status_code}): {error_text[:200]}. "
                                        "Retrying without usage tracking."
                                    )
                                    payload.pop("stream_options", None)
                                    break  # break inner stream context, retry loop continues

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

                            if line.startswith("data: "):
                                data = line[6:]  # Remove "data: " prefix
                                if data == "[DONE]":
                                    break

                                try:
                                    chunk = json.loads(data)

                                    # Check for usage data (sent as final chunk with stream_options)
                                    if "usage" in chunk and chunk["usage"]:
                                        usage = chunk["usage"]
                                        yield f"data: {json.dumps({'usage': usage})}\n\n"

                                    if "choices" in chunk and chunk["choices"]:
                                        delta = chunk["choices"][0].get("delta", {})
                                        if "content" in delta:
                                            content = delta["content"]
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse JSON chunk: {data} - Error: {e}")
                                    continue

                        logger.debug(f"Stream completed: {line_count} lines received")
                        return  # success — do not retry
                                
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
