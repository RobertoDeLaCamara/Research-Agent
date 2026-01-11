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
def bypass_proxy_for_ollama():
    """Ensure Ollama host and common local addresses are in NO_PROXY."""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        from urllib.parse import urlparse
        hostname = urlparse(ollama_url).hostname
        
        # Base local addresses to always bypass
        bypass_hosts = {"localhost", "127.0.0.1"}
        if hostname:
            bypass_hosts.add(hostname)
            
        no_proxy = os.getenv("NO_PROXY", "")
        current_no_proxy = set(x.strip() for x in no_proxy.split(",") if x.strip())
        
        if not bypass_hosts.issubset(current_no_proxy):
            current_no_proxy.update(bypass_hosts)
            new_no_proxy = ",".join(current_no_proxy)
            os.environ["NO_PROXY"] = new_no_proxy
            os.environ["no_proxy"] = new_no_proxy
            logging.debug(f"Updated NO_PROXY to: {new_no_proxy}")
    except Exception as e:
        logging.warning(f"Failed to setup proxy bypass: {e}")

def get_max_results(state: dict) -> int:
    """Determine max results based on research depth from state."""
    depth = state.get("research_depth", "standard")
    mapping = {
        "quick": 2,
        "standard": 5,
        "deep": 10
    }
    return mapping.get(depth, 5)
