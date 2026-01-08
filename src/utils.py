import logging
import os
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings

def setup_logging(level: str = None) -> logging.Logger:
    """Setup logging configuration."""
    log_level = level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def validate_env_vars() -> bool:
    """Validate required environment variables."""
    required_vars = ["OLLAMA_BASE_URL"]
    optional_vars = ["TAVILY_API_KEY", "GITHUB_TOKEN", "EMAIL_USERNAME"]
    
    missing_required = [var for var in required_vars if not getattr(settings, var.lower(), None)]
    
    if missing_required:
        raise ValueError(f"Missing required environment variables: {missing_required}")
    
    missing_optional = [var for var in optional_vars if not getattr(settings, var.lower(), None)]
    if missing_optional:
        logging.warning(f"Optional environment variables not set: {missing_optional}")
    
    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def api_call_with_retry(func, *args, **kwargs):
    """Retry failed API calls with exponential backoff."""
    logger = logging.getLogger(__name__)
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"API call failed: {e}, retrying...")
        raise
