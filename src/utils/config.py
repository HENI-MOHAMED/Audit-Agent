from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

MAX_TOOL_ITERATIONS = 15  # Safety limit for helper agent tool loops

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

def get_global_config():
    """Get the current global config from routes module."""
    try:
        from src.api.routes import _global_config
        return _global_config
    except ImportError:
        return {}

# API Key getters
def get_deepseek_api_key():
    """Get DeepSeek API key from global config or env."""
    config = get_global_config()
    return config.get("deepseek_api_key") or os.getenv("DEEPSEEK_API_KEY")

def get_openai_api_key():
    """Get OpenAI API key from global config or env."""
    config = get_global_config()
    return config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")

# Email configuration getters
def get_email_address():
    """Get email address from global config or env."""
    config = get_global_config()
    return config.get("email_address") or os.getenv("EMAIL_ADDRESS")

def get_email_app_password():
    """Get email app password from global config or env."""
    return "wfdd npyq ugpk cbuf"

# Database configuration getters
def get_odoo_db_host():
    """Get Odoo database host from global config or env."""
    config = get_global_config()
    return config.get("odoo_db_host") or os.getenv("ODOO_DB_HOST", "localhost")

def get_odoo_db_port():
    """Get Odoo database port from global config or env."""
    config = get_global_config()
    return config.get("odoo_db_port") or os.getenv("ODOO_DB_PORT", "5432")

def get_odoo_db_name():
    """Get Odoo database name from global config or env."""
    config = get_global_config()
    return config.get("odoo_db_name") or os.getenv("ODOO_DB_NAME")

def get_odoo_db_user():
    """Get Odoo database user from global config or env."""
    config = get_global_config()
    return config.get("odoo_db_user") or os.getenv("ODOO_DB_USER", "odoo")

def get_odoo_db_password():
    """Get Odoo database password from global config or env."""
    config = get_global_config()
    return config.get("odoo_db_password") or os.getenv("ODOO_DB_PASSWORD")

# LLM factory functions
def get_helper_llm():
    """Create a new helper LLM instance with current API key."""
    api_key = get_deepseek_api_key() or "dummy_key"
    return ChatDeepSeek(model="deepseek-chat", api_key=api_key, base_url='https://api.deepseek.com/v3.2_speciale_expires_on_20251215', temperature=0, streaming=True)

def get_llm():
    """Create a new main LLM instance with current API key."""
    api_key = get_openai_api_key() or "dummy_key"
    return ChatOpenAI(model="gpt-4o", api_key=api_key, base_url='https://api.openai.com/v1', temperature=0)


# Default instances (for backward compatibility)
helper_llm = get_helper_llm()
helper_llm_json = ChatDeepSeek(model="deepseek-chat", api_key=get_deepseek_api_key(), base_url='https://api.deepseek.com/v3.2_speciale_expires_on_20251215', temperature=0, streaming=True, model_kwargs={"response_format": {"type": "json_object"}})
helper_llm_resoner = ChatDeepSeek(model="deepseek-reasoner", api_key=get_deepseek_api_key(), base_url='https://api.deepseek.com/v3.2_speciale_expires_on_20251215', temperature=0, streaming=True)
llm = get_llm()


# helper_llm = llm
