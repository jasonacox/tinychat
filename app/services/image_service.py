"""Image generation service for SwarmUI and OpenAI."""

import base64
import io
import logging
from typing import Optional

import aiohttp
from PIL import Image

from app.config import Settings

logger = logging.getLogger("tinychat")


class ImageService:
    """Service for generating images via SwarmUI or OpenAI."""
    
    @staticmethod
    async def generate_image(prompt: str) -> dict:
        """
        Generate an image using SwarmUI or OpenAI and return a data URI.
        
        Args:
            prompt: The text prompt for image generation
            
        Returns:
            dict: A dictionary containing the prompt and image data URI, or error information
        """
        logger.info(f"Image provider: {Settings.IMAGE_PROVIDER}")
        
        if Settings.IMAGE_PROVIDER == "swarmui":
            image_encoded = await ImageService._generate_swarmui(prompt)
        elif Settings.IMAGE_PROVIDER == "openai":
            image_encoded = await ImageService._generate_openai(prompt)
        else:
            logger.error(f"Unknown IMAGE_PROVIDER: {Settings.IMAGE_PROVIDER}")
            return {"error": "Unsupported image provider"}
        
        if not image_encoded:
            logger.error(f"Image generation failed for prompt: {prompt}")
            return {"error": "Generation failed"}
        
        # Normalize to raw base64 payload
        if "," in image_encoded:
            image_b64 = image_encoded.split(",", 1)[1]
        else:
            image_b64 = image_encoded
        
        logger.info(f"Received image data (bytes ~ {len(image_b64)})")
        
        try:
            image = Image.open(io.BytesIO(base64.b64decode(image_b64)))
        except Exception:
            return {"error": "Unable to decode image data"}
        
        # Resize down for web if necessary
        max_dim = 1024
        if image.width > max_dim or image.height > max_dim:
            image.thumbnail((max_dim, max_dim))
        # Convert to JPEG for browser-friendliness
        if image.mode == "RGBA":
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        out_b64 = base64.b64encode(out.getvalue()).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{out_b64}"
        
        return {"prompt": prompt, "image_data": data_uri}
    
    @staticmethod
    async def _generate_swarmui(prompt: str) -> Optional[str]:
        """Generate image using SwarmUI."""
        logger.info(f"Sending prompt to SwarmUI ({Settings.SWARMUI}) model={Settings.IMAGE_MODEL}")
        logger.info(f"Prompt: {prompt}")
        
        async def _get_session_id(session: aiohttp.ClientSession) -> Optional[str]:
            try:
                async with session.post(
                    f"{Settings.SWARMUI.rstrip('/')}/API/GetNewSession", 
                    json={}, 
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("session_id")
            except Exception as e:
                logger.error(f"Error getting session id from SwarmUI: {e}")
            return None
        
        async def _call_generate(
            session: aiohttp.ClientSession, 
            session_id: str, 
            prompt_text: str
        ) -> Optional[str]:
            params = {
                "model": Settings.IMAGE_MODEL,
                "width": Settings.IMAGE_WIDTH,
                "height": Settings.IMAGE_HEIGHT,
                "cfgscale": Settings.IMAGE_CFGSCALE,
                "steps": Settings.IMAGE_STEPS,
                "seed": Settings.IMAGE_SEED,
            }
            raw_input = {
                "prompt": str(prompt_text), 
                **{k: v for k, v in params.items()}, 
                "donotsave": True
            }
            data = {
                "session_id": session_id,
                "images": "1",
                "prompt": str(prompt_text),
                **{k: str(v) for k, v in params.items()},
                "donotsave": True,
                "rawInput": raw_input,
            }
            try:
                async with session.post(
                    f"{Settings.SWARMUI.rstrip('/')}/API/GenerateText2Image", 
                    json=data, 
                    timeout=Settings.IMAGE_TIMEOUT
                ) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        imgs = j.get("images") or []
                        if imgs:
                            return imgs[0]
                    else:
                        logger.error(f"SwarmUI GenerateText2Image returned status {resp.status}")
            except Exception as e:
                logger.error(f"Error calling SwarmUI GenerateText2Image: {e}")
            return None
        
        image_encoded = None
        try:
            async with aiohttp.ClientSession() as session:
                session_id = await _get_session_id(session)
                if not session_id:
                    logger.error("Unable to obtain SwarmUI session id")
                    return None
                image_encoded = await _call_generate(session, session_id, prompt)
        except Exception as e:
            logger.error(f"Unexpected error during SwarmUI generation: {e}")
            return None
        
        return image_encoded
    
    @staticmethod
    async def _generate_openai(prompt: str) -> Optional[str]:
        """Generate image using OpenAI."""
        logger.info(f"Sending prompt to OpenAI Images API ({Settings.OPENAI_IMAGE_API_BASE}) model={Settings.OPENAI_IMAGE_MODEL}")
        logger.info(f"Prompt: {prompt}")
        
        async def _call_openai(session: aiohttp.ClientSession, prompt_text: str) -> Optional[str]:
            url = f"{Settings.OPENAI_IMAGE_API_BASE.rstrip('/')}/images/generations"
            headers = {
                "Authorization": f"Bearer {Settings.OPENAI_IMAGE_API_KEY}", 
                "Content-Type": "application/json"
            }
            body = {
                "model": Settings.OPENAI_IMAGE_MODEL, 
                "prompt": prompt_text, 
                "size": Settings.OPENAI_IMAGE_SIZE
            }
            try:
                async with session.post(
                    url, 
                    json=body, 
                    headers=headers, 
                    timeout=Settings.IMAGE_TIMEOUT
                ) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        data = j.get("data") or []
                        if data:
                            first = data[0]
                            if "b64_json" in first:
                                return first["b64_json"]
                            if "url" in first:
                                # Fetch binary and return as base64
                                img_url = first["url"]
                                async with session.get(img_url) as img_resp:
                                    if img_resp.status == 200:
                                        b = await img_resp.read()
                                        return base64.b64encode(b).decode("utf-8")
                    else:
                        text = await resp.text()
                        logger.error(f"OpenAI images API returned {resp.status}: {text}")
            except Exception as e:
                logger.error(f"Error calling OpenAI Images API: {e}")
            return None
        
        image_encoded = None
        try:
            async with aiohttp.ClientSession() as session:
                image_encoded = await _call_openai(session, prompt)
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI generation: {e}")
            return None
        
        return image_encoded
