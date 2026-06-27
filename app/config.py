"""
Configuration management for TinyChat.

Centralizes all environment variable loading and validation.
"""
import os
import logging
from typing import Any, Dict, List, Optional

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
    # Allow clients to send system-role messages.
    # Default: False (strip system messages for security).
    # Set to True only in trusted/local deployments where users are known.
    ALLOW_SYSTEM_MESSAGES: bool = os.getenv("ALLOW_SYSTEM_MESSAGES", "false").lower() == "true"
    ENABLE_DEBUG_LOGS: bool = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"
    ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS", "*").split(",")
    # CORS allowed origins.
    # Default (ALLOWED_ORIGINS not set): ["*"] — permissive, matches original behavior,
    #   preserves compatibility for existing installs.
    # Recommended for production: set ALLOWED_ORIGINS to your domain(s) to restrict
    #   cross-origin access and protect against session hijacking if auth is added.
    #
    # Examples:
    #   ALLOWED_ORIGINS=https://chat.example.com
    #   ALLOWED_ORIGINS=https://chat.example.com,https://app.example.com
    _origins_env: str = os.getenv("ALLOWED_ORIGINS", "")
    _parsed_origins: List[str] = (
        [o.strip() for o in _origins_env.split(",") if o.strip()]
        if _origins_env.strip()
        else ["*"]
    )
    # Normalize: if "*" appears alongside explicit origins, treat as wildcard.
    # Mixing wildcard with named origins is invalid per CORS spec when
    # credentials are enabled.
    if "*" in _parsed_origins and len(_parsed_origins) > 1:
        logger.warning(
            "⚠️  ALLOWED_ORIGINS contains '*' alongside explicit origins — "
            "normalizing to wildcard-only. Remove '*' if you meant to restrict."
        )
        _parsed_origins = ["*"]
    ALLOWED_ORIGINS: List[str] = _parsed_origins
    
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
    
    # Document Upload Configuration
    MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
    MAX_DOCUMENTS_IN_CONTEXT: int = int(os.getenv("MAX_DOCUMENTS_IN_CONTEXT", "1"))
    SUPPORTED_DOCUMENT_TYPES: List[str] = [
        "text/plain",           # .txt
        "text/markdown",        # .md
        "text/csv",             # .csv
        "application/pdf",      # .pdf
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
        "application/vnd.openxmlformats-officedocument.presentationml.presentation", # .pptx
        "application/json",     # .json
        "text/html",            # .html
    ]
    
    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 5
    
    # Available models
    AVAILABLE_MODELS: List[str] = []

    # Multi-backend configuration
    # Format: "name|url|key|models;name2|url2|key2|models2"
    # Falls back to single OPENAI_API_URL/KEY if not set.
    API_BACKENDS: List[Dict[str, Any]] = []

    # RLM availability (set during initialization)
    HAS_RLM: bool = False
    
    @classmethod
    def initialize(cls):
        """Initialize and validate configuration."""
        # Parse multi-backend configuration
        cls._parse_backends()

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
            from rlm import RLM  # Try to import the actual class
            cls.HAS_RLM = True
        except (ImportError, AttributeError):
            cls.HAS_RLM = False

        cls._log_configuration()

    @classmethod
    def _parse_backends(cls):
        """
        Parse the API_BACKENDS env var into a list of backend configs.

        Format: "name|url|key|models;name2|url2|key2|models2"
        Example: "Ollama|http://localhost:11434/v1|ollama|llama3,codellama;OpenRouter|https://openrouter.ai/api/v1|sk-xxx|claude-3,gpt-4"

        Falls back to a single "default" backend built from OPENAI_API_URL/KEY
        and AVAILABLE_MODELS if API_BACKENDS is not set.
        """
        backends_str = os.getenv("API_BACKENDS", "")
        cls.API_BACKENDS = []

        if backends_str.strip():
            for entry in backends_str.split(";"):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split("|")
                if len(parts) < 3:
                    logger.warning(f"⚠️  Skipping malformed backend entry: '{entry}' (need at least name|url|key)")
                    continue
                name = parts[0].strip()
                url = parts[1].strip()
                key = parts[2].strip()
                models_csv = parts[3].strip() if len(parts) > 3 else ""
                models = [m.strip() for m in models_csv.split(",") if m.strip()] if models_csv else []
                cls.API_BACKENDS.append({
                    "name": name,
                    "url": url,
                    "key": key,
                    "models": models,
                })
            if cls.API_BACKENDS:
                logger.info(f"  Multi-backend: {len(cls.API_BACKENDS)} backend(s) configured")

        # If no backends configured, build a default from the single-endpoint vars
        if not cls.API_BACKENDS:
            models_str = os.getenv("AVAILABLE_MODELS", f"{cls.DEFAULT_MODEL},gpt-3.5-turbo,gpt-4,gpt-4-turbo")
            default_models = [m.strip() for m in models_str.split(",") if m.strip()]
            cls.API_BACKENDS.append({
                "name": "default",
                "url": cls.OPENAI_API_URL,
                "key": cls.OPENAI_API_KEY,
                "models": default_models,
            })

    @classmethod
    def get_backend(cls, name: Optional[str] = None) -> Optional[Dict]:
        """
        Get a backend config by name.

        Returns the first backend when name is None (no preference).
        Returns None when a specific name is requested but not found,
        so the caller can reject explicitly instead of silently falling
        back to the wrong backend.
        """
        if not name:
            return cls.API_BACKENDS[0] if cls.API_BACKENDS else None
        for backend in cls.API_BACKENDS:
            if backend["name"] == name:
                return backend
        return None  # explicit name not found — don't silently fall back
    
    @classmethod
    def _log_configuration(cls):
        """Log current configuration at startup."""
        logger.info(f"TinyChat v{cls.VERSION} starting with config:")
        logger.info(f"  API URL: {cls.OPENAI_API_URL}")
        logger.info(f"  API Key: {'***' + cls.OPENAI_API_KEY[-4:] if cls.OPENAI_API_KEY else 'NOT SET'}")
        logger.info(f"  Default Model: {cls.DEFAULT_MODEL}")
        logger.info(f"  Available Models: {cls.AVAILABLE_MODELS}")
        if len(cls.API_BACKENDS) > 1:
            logger.info(f"  Backends: {', '.join(b['name'] for b in cls.API_BACKENDS)}")
        logger.info(f"  Default Temperature: {cls.DEFAULT_TEMPERATURE}")
        logger.info(f"  Security: Max message length {cls.MAX_MESSAGE_LENGTH}")
        logger.info(f"  Security: Max conversation history {cls.MAX_CONVERSATION_HISTORY}")
        if cls.ALLOW_SYSTEM_MESSAGES:
            logger.warning(f"  ⚠️  Security: ALLOW_SYSTEM_MESSAGES=true — clients can inject system prompts")
        else:
            logger.info(f"  Security: Client system messages stripped ✓")
        
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
