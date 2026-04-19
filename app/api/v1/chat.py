"""Chat streaming endpoint."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest
from app.rate_limiter import limiter, RATE_LIMIT
from app.config import Settings
from app.services.llm_service import LLMService
from app.services.rlm_service import RLMService
from app.services.image_service import ImageService
from app.services.logging_service import LoggingService
from app.utils.security import get_client_ip
from app.utils.state import StateManager

logger = logging.getLogger("tinychat")

router = APIRouter()


@router.post("/api/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(request: Request, chat_request: ChatRequest = None):
    """
    Stream chat completions via Server-Sent Events (stateless endpoint).
    
    This is the main chat endpoint. It receives the full conversation history
    from the client, forwards it to the LLM API, and streams the response back.
    The server is stateless - all conversation state is managed client-side.
    
    Args:
        request: The HTTP request context (required by slowapi rate limiter)
        chat_request: ChatRequest with messages array, optional temperature and model
        
    Returns:
        StreamingResponse: SSE stream of response chunks
        
    Raises:
        HTTPException: 500 if API key is not configured
    """
    client_ip = get_client_ip(request)
    
    # Determine which model will be used
    model_to_use = chat_request.model or Settings.DEFAULT_MODEL
    temp_to_use = chat_request.temperature or Settings.DEFAULT_TEMPERATURE
    
    logger.debug(f"Chat stream request from {client_ip}: {len(chat_request.messages)} messages")
    logger.debug(f"  Model: {model_to_use} (requested: {chat_request.model or 'default'})")
    logger.debug(f"  Temperature: {temp_to_use}")

    # SECURITY: Strip client-injected system role messages.
    # These can be used to override model behavior or extract training data.
    # Server-side system prompts (if any) are injected later in the pipeline,
    # so stripping here only affects client-supplied messages.
    # NOTE: If additional roles (e.g., 'developer') are added to the request
    # schema in the future, add them to restricted_roles below.
    if not Settings.ALLOW_SYSTEM_MESSAGES:
        restricted_roles = {"system"}
        stripped = [m for m in chat_request.messages if m.get("role") in restricted_roles]
        if stripped:
            logger.warning(
                f"⚠️  Stripped {len(stripped)} system message(s) from {client_ip} — "
                f"ALLOW_SYSTEM_MESSAGES=false"
            )
            chat_request.messages = [
                m for m in chat_request.messages if m.get("role") not in restricted_roles
            ]
            # If all messages were system messages, reject the request
            if not chat_request.messages:
                logger.warning(f"Rejected request from {client_ip}: all messages were system role")
                raise HTTPException(
                    status_code=400,
                    detail="Request contained only system messages. Include at least one user or assistant message."
                )
    
    # Validate API key
    if not Settings.OPENAI_API_KEY:
        logger.error("API key not configured")
        raise HTTPException(status_code=500, detail="API key not configured")
    
    # Track session if provided
    if chat_request.session_id:
        await StateManager.track_session(chat_request.session_id)
    
    # Check if this is an image generation request
    last_message = chat_request.messages[-1]["content"] if chat_request.messages else ""
    last_message_lower = last_message.strip().lower()
    is_image_request = last_message_lower.startswith("@image") or last_message_lower.startswith("/image")
    
    if is_image_request:
        # Remove the command prefix (@image or /image)
        if last_message_lower.startswith("@image"):
            image_prompt = last_message.strip()[6:].strip()
        else:  # /image
            image_prompt = last_message.strip()[6:].strip()
        
        async def image_gen():
            await StateManager.increment_generations()
            
            try:
                logger.info(f"Image generation request from {client_ip}: {image_prompt}")
                
                # Send initial message
                yield f"data: {json.dumps({'content': 'Generating image...'})}\n\n"
                
                # Generate the image
                result = await ImageService.generate_image(image_prompt)
                
                if "error" in result:
                    error_msg = f"Error generating image: {result['error']}"
                    yield f"data: {json.dumps({'content': error_msg})}\n\n"
                else:
                    # Send the image data
                    response_data = {
                        'image': result['image_data'], 
                        'content': 'Here is your image.'
                    }
                    yield f"data: {json.dumps(response_data)}\n\n"
                    
                    # Log conversation
                    LoggingService.log_conversation(
                        chat_request.messages, 
                        f"[Generated image: {image_prompt}]", 
                        "image-gen", 
                        0.0
                    )
            except Exception as e:
                logger.error(f"Error in image generation: {e}")
                yield f"data: {json.dumps({'content': 'Failed to generate image.'})}\n\n"
            finally:
                await StateManager.decrement_generations()
        
        return StreamingResponse(
            image_gen(), 
            media_type="text/plain", 
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    
    # Handle RLM requests
    if chat_request.rlm:
        if not Settings.HAS_RLM:
            async def rlm_missing_gen():
                yield f"data: {json.dumps({'error': 'RLM module not installed. Please rebuild the container with RLM support.'})}\n\n"
            return StreamingResponse(rlm_missing_gen(), media_type="text/event-stream")
        
        # SECURITY: Validate RLM passcode on backend
        if Settings.RLM_PASSCODE:
            if not chat_request.rlm_passcode:
                logger.warning(f"🚫 RLM request without passcode from {client_ip}")
                async def rlm_auth_error_gen():
                    yield f"data: {json.dumps({'error': 'RLM access requires authentication. Please enable RLM through the web interface.'})}\n\n"
                return StreamingResponse(rlm_auth_error_gen(), media_type="text/event-stream")
            
            if chat_request.rlm_passcode != Settings.RLM_PASSCODE:
                logger.warning(f"🚫 RLM request with INVALID passcode from {client_ip}")
                async def rlm_invalid_passcode_gen():
                    yield f"data: {json.dumps({'error': 'Invalid RLM passcode. Access denied.'})}\n\n"
                return StreamingResponse(rlm_invalid_passcode_gen(), media_type="text/event-stream")
            
            logger.info(f"✓ RLM passcode validated for {client_ip}")
        
        async def rlm_generate():
            await StateManager.increment_generations()
            
            # Check RLM concurrency limit
            if not await StateManager.check_rlm_capacity():
                yield f"data: {json.dumps({'error': 'Too many concurrent RLM requests. Please try again later.'})}\n\n"
                await StateManager.decrement_generations()
                return
            
            await StateManager.increment_rlm_generations()
            
            try:
                rlm_count = await StateManager.get_active_rlm_generations()
                logger.info(f"RLM generation request from {client_ip} for model: {model_to_use} (active RLM: {rlm_count})")
                
                # Extract document context from most recent messages (limit by MAX_DOCUMENTS_IN_CONTEXT)
                document_context = None
                documents_found = 0
                for msg in reversed(chat_request.messages):
                    if msg.get("document") and documents_found < Settings.MAX_DOCUMENTS_IN_CONTEXT:
                        doc = msg["document"]
                        if document_context is None:
                            document_context = f"# Document: {doc['name']}\n\n{doc['markdown']}"
                        else:
                            document_context = f"{document_context}\n\n---\n\n# Document: {doc['name']}\n\n{doc['markdown']}"
                        documents_found += 1
                
                # Stream RLM completion
                assistant_full_content = ""
                async for chunk in RLMService.stream_rlm_completion(
                    chat_request.messages, 
                    model_to_use,
                    chat_request.show_rlm_thinking,
                    document_context
                ):
                    yield chunk
                    # Extract content for logging
                    if 'content' in chunk:
                        try:
                            data = json.loads(chunk.split("data: ", 1)[1])
                            if 'content' in data:
                                assistant_full_content += data['content']
                        except:
                            pass
                
                # Log conversation
                LoggingService.log_conversation(
                    chat_request.messages, 
                    assistant_full_content, 
                    f"{model_to_use}-rlm", 
                    temp_to_use
                )
            finally:
                await StateManager.decrement_generations()
                await StateManager.decrement_rlm_generations()
        
        return StreamingResponse(
            rlm_generate(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    
    # Standard LLM streaming
    async def stream_response():
        await StateManager.increment_generations()
        
        try:
            # Inject document context for non-RLM mode
            messages_with_docs = LLMService.inject_document_context(chat_request.messages)
            
            assistant_full_content = ""
            async for chunk in LLMService.stream_completion(
                messages_with_docs, 
                temp_to_use, 
                model_to_use
            ):
                yield chunk
                # Extract content for logging
                if 'content' in chunk:
                    try:
                        data = json.loads(chunk.split("data: ", 1)[1])
                        if 'content' in data:
                            assistant_full_content += data['content']
                    except:
                        pass
            
            # Log conversation
            LoggingService.log_conversation(
                chat_request.messages, 
                assistant_full_content, 
                model_to_use, 
                temp_to_use
            )
        finally:
            await StateManager.decrement_generations()
    
    return StreamingResponse(
        stream_response(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
