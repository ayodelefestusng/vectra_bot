import os
import logging
from typing import Optional
from sqlalchemy import text
from .database import SessionLocal
from .ollama_service import OllamaService

logger = logging.getLogger("HR_AGENT")

_llm = None

# Constants / Fallbacks
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# Remote config
OLLAMA_REMOTE_URL = "https://ai.notchhr.io/api/chat/local"
OLLAMA_USERNAME = "ai-user"
OLLAMA_PASSWORD = "x2GS7jEF@#2T"
OLLAMA_MODEL = "gpt-oss-safeguard:20b"

def get_llm_instance(tenant_id=None):
    """
    Fetches LLM configuration and returns an instance of OllamaService.
    """
    try:
        # Default fallback to remote Ollama if no DB config found
        logger.info("🌐 Initializing Ollama Cloud LLM instance")
        return OllamaService(
            base_url=OLLAMA_REMOTE_URL,
            username=OLLAMA_USERNAME,
            password=OLLAMA_PASSWORD,
            model=OLLAMA_MODEL
        )
    except Exception as e:
        logger.error(f"❌ Error in get_llm_instance: {e}")
        return None

def get_model():
    """
    Lazy-loads the model and binds tools only when needed.
    """
    global _llm
    
    if _llm is not None:
        return _llm

    try:
        base_llm = get_llm_instance()
        if base_llm is not None:
            _llm = base_llm
            logger.info("✅ Model and tools initialized successfully.")
            return _llm
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_model: {e}", exc_info=True)
    
    return None


