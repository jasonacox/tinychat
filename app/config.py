"""
Configuration management for TinyChat.

Centralizes all environment variable loading and validation.
"""
import os
import logging
from typing import List

logger = logging.getLogger("tinychat")

# Import version from package
try:
    from app import __version__
except ImportError:
    __version__ = "unknown"


class Settings:
    """Application settings loaded from environment variables."""
    
    # Version (imported from app/__init__.py)
    VERSION = __version__
    
    # API Configuration
    OPENAI_API_URL: str = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")
    DEFAULT_TEMPERATURE: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
    
    # Security Configuration
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "262144"))
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))
    ENABLE_DEBUG_LOGS: bool = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"
    ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS", "*").split(",")
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    
    # Research/Logging Configuration
    CHAT_LOG: str = os.getenv("CHAT_LOG", "")
    
    # Image Generation Configuration
    IMAGE_PROVIDER: str = os.getenv("IMAGE_PROVIDER", "swarmui").lower()
    
    # SwarmUI settings
    SWARMUI: str = os.getenv("SWARMUI", "http://localhost:7801")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "Flux/flux1-schnell-fp8")
    IMAGE_CFGSCALE: float = float(os.getenv("IMAGE_CFGSCALE", "1.0"))
    IMAGE_STEPS: int = int(os.getenv("IMAGE_STEPS", "6"))
    IMAGE_WIDTH: int = int(os.getenv("IMAGE_WIDTH", "1024"))
    IMAGE_HEIGHT: int = int(os.getenv("IMAGE_HEIGHT", "1024"))
    IMAGE_SEED: int = int(os.getenv("IMAGE_SEED", "-1"))
    IMAGE_TIMEOUT: int = int(os.getenv("IMAGE_TIMEOUT", "300"))
    
    # OpenAI image settings
    OPENAI_IMAGE_API_KEY: str = os.getenv("OPENAI_IMAGE_API_KEY", "")
    OPENAI_IMAGE_API_BASE: str = os.getenv("OPENAI_IMAGE_API_BASE", "https://api.openai.com/v1")
    OPENAI_IMAGE_MODEL: str = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
    OPENAI_IMAGE_SIZE: str = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
    
    # RLM Configuration
    RLM_TIMEOUT: int = int(os.getenv("RLM_TIMEOUT", "60"))
    MAX_CONCURRENT_RLM: int = int(os.getenv("MAX_CONCURRENT_RLM", "3"))
    RLM_PASSCODE: str = os.getenv("RLM_PASSCODE", "")
    
    # Image Upload & Vision Configuration
    MAX_IMAGE_SIZE_MB: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
    SUPPORTED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    MAX_IMAGES_IN_CONTEXT: int = int(os.getenv("MAX_IMAGES_IN_CONTEXT", "1"))
    
    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 5
    
    # Available models
    AVAILABLE_MODELS: List[str] = []
    
    @classmethod
    def initialize(cls):
        """Initialize and validate configuration."""
        # Parse available models
        models_str = os.getenv("AVAILABLE_MODELS", f"{cls.DEFAULT_MODEL},gpt-3.5-turbo,gpt-4,gpt-4-turbo")
        cls.AVAILABLE_MODELS = list(dict.fromkeys([
            model.strip() for model in models_str.split(",") if model.strip()
        ]))
        
        # Ensure DEFAULT_MODEL is in AVAILABLE_MODELS
        if cls.DEFAULT_MODEL not in cls.AVAILABLE_MODELS:
            logger.warning(f"⚠️  Configuration issue: DEFAULT_MODEL '{cls.DEFAULT_MODEL}' not in AVAILABLE_MODELS")
            logger.warning(f"   Adding '{cls.DEFAULT_MODEL}' to available models list")
            cls.AVAILABLE_MODELS.insert(0, cls.DEFAULT_MODEL)
        
        # Check for RLM
        try:
            import rlm
            cls.HAS_RLM = True
        except ImportError:
            cls.HAS_RLM = False
        
        cls._log_configuration()
    
    @classmethod
    def _log_configuration(cls):
        """Log current configuration at startup."""
        logger.info(f"TinyChat v{cls.VERSION} starting with config:")
        logger.info(f"  API URL: {cls.OPENAI_API_URL}")
        logger.info(f"  API Key: {'***' + cls.OPENAI_API_KEY[-4:] if cls.OPENAI_API_KEY else 'NOT SET'}")
        logger.info(f"  Default Model: {cls.DEFAULT_MODEL}")
        logger.info(f"  Available Models: {cls.AVAILABLE_MODELS}")
        logger.info(f"  Default Temperature: {cls.DEFAULT_TEMPERATURE}")
        logger.info(f"  Security: Max message length {cls.MAX_MESSAGE_LENGTH}")
        logger.info(f"  Security: Max conversation history {cls.MAX_CONVERSATION_HISTORY}")
        
        if cls.HAS_RLM:
            logger.info(f"  RLM: Enabled (timeout={cls.RLM_TIMEOUT}s, max_concurrent={cls.MAX_CONCURRENT_RLM})")
            if cls.RLM_PASSCODE:
                logger.info(f"  RLM Security: Passcode protection enabled ✓")
            else:
                logger.warning(f"  ⚠️  RLM Security: No passcode set - RLM accessible to all users!")
            logger.warning(f"  ⚠️  RLM Security: Code execution enabled - use only with trusted users!")
        else:
            logger.info(f"  RLM: Not available (rlm package not installed)")
        
        if cls.CHAT_LOG:
            logger.info(f"  Research: Logging conversations to {cls.CHAT_LOG}")
        
        logger.info(f"  Image Generation: Provider={cls.IMAGE_PROVIDER}")
        if cls.IMAGE_PROVIDER == "swarmui":
            logger.info(f"  Image Generation: SwarmUI={cls.SWARMUI}, Model={cls.IMAGE_MODEL}")
        elif cls.IMAGE_PROVIDER == "openai":
            logger.info(f"  Image Generation: OpenAI Model={cls.OPENAI_IMAGE_MODEL}")


# Initialize settings on module load
Settings.initialize()
