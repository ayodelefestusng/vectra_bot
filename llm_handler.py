from .database import SessionLocal
from .ollama_service import OllamaService
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from .logger_utils import log_info, log_error, log_debug, log_warning, logger
from sqlalchemy import text
from langchain.chat_models import init_chat_model

import os   
from dotenv import load_dotenv
load_dotenv()

OLLAMA_BASE_URL = "https://ai.notchhr.io/api/chat/local"
OLLAMA_USERNAME = "ai-user"
OLLAMA_PASSWORD = "x2GS7jEF@#2T"
OLLAMA_MODEL = "gpt-oss-safeguard:20b"
GEMINI_INIT= os.getenv("GEMINI_INIT", "google_genai:gemini-flash-latest")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# Constants / Fallbacks
# OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
# DEFAULT_AGENT_PROMPT = 
llm_fallback = init_chat_model(GEMINI_INIT, temperature=0)
model = llm_fallback  # Consistent naming for the primary LLM
_llm = None
def get_llm_instance(llm_config=None):
    logger.info(f"🌐 get_llm_instance called")
    """
    Returns an LLM instance based on the provided configuration or global DB setting.
    
    Supported LLM types:
    - gemini: Google Gemini API
    - ollama: Local Ollama instance
    - ollama_cloud: Ollama Cloud API (requires OLLAMA_API_KEY)
    """
    # If explicit config passed, use it. Otherwise fetch global if needed.
    # Note: 'llm_config' here is expected to be a Django ORM object or None.
    with SessionLocal() as session:
        sql = "SELECT name, model FROM customer_llm LIMIT 1"
        res = session.execute(text(sql)).fetchone()
        
        # If no config is found in the DB, default to a safe fallback
        if not res:
            logger.warning("No LLM config found in DB, defaulting to Gemini.")
            return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
        
        name = res[0].lower() if res[0] else "gemini"
        model_name = res[1] or "gemini-1.5-flash"
        logger.info(f"🌐 Initializing LLM ALERT: {name} - {model_name}")
        if "gemini" in name:
            return ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv("GOOGLE_API_KEY"), temperature=0)
            
        elif "ollama" in name:
            # Initialize OllamaService without local network parameters
            return OllamaService(model=model_name)
            # return OllamaCloudWrapper(
            #     model_name=model_name,
            #     host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
            #     api_key=os.getenv("OLLAMA_API_KEY", "")
            # )
            
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=os.getenv("GOOGLE_API_KEY"), temperature=0)

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
            # Replaced with standardized tool list
            from .tools import tools
            # _llm = base_llm.bind_tools(tools)
            logger.info("✅ Model and tools initialized successfully.")
            return base_llm
        else:
            logger.error("❌ Failed to initialize base LLM.")
            return None
    except Exception as e:
        logger.error(f"❌ Error initializing model/tools: {e}")
        return None
embeddings = None
def get_embeddings():
    global embeddings
    if embeddings is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("❌ GEMINI_API_KEY or GOOGLE_API_KEY not found in environment.")
            raise ValueError("No API key found for embeddings. Set GEMINI_API_KEY or GOOGLE_API_KEY.")
        
        try:
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
            logger.info("✅ Embeddings model initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Embeddings: {e}")
            raise
    return embeddings



 

# import os
# import logging
# from typing import Optional
# from sqlalchemy import text
# from .database import SessionLocal
# from .ollama_service import OllamaService

# logger = logging.getLogger("HR_AGENT")

# _llm = None

# # Constants / Fallbacks
# OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# # Remote config
# OLLAMA_REMOTE_URL = "https://ai.notchhr.io/api/chat/local"
# OLLAMA_USERNAME = "ai-user"
# OLLAMA_PASSWORD = "x2GS7jEF@#2T"
# OLLAMA_MODEL = "gpt-oss:120b"

# def get_llm_instancev1(tenant_id=None):
#     """
#     Fetches LLM configuration and returns an instance of OllamaService.
#     """
#     try:
#         # Default fallback to remote Ollama if no DB config found
#         logger.info("🌐 Initializing Ollama Cloud LLM instance")
#         return OllamaService(
#             base_url=OLLAMA_REMOTE_URL,
#             username=OLLAMA_USERNAME,
#             password=OLLAMA_PASSWORD,
#             model=OLLAMA_MODEL
#         )
#     except Exception as e:
#         logger.error(f"❌ Error in get_llm_instance: {e}")
#         return None

# def get_modelv1():
#     """
#     Lazy-loads the model and binds tools only when needed.
#     """
#     global _llm
    
#     if _llm is not None:
#         return _llm

#     try:
#         base_llm = get_llm_instance()
#         if base_llm is not None:
#             _llm = base_llm
#             logger.info("✅ Model and tools initialized successfully.")
#             return _llm
        
#     except Exception as e:
#         logger.error(f"❌ Unexpected error in get_model: {e}", exc_info=True)
    
#     return None


