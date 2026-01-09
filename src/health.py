import requests
import shutil
import logging
from typing import Dict, Tuple
from config import settings

logger = logging.getLogger(__name__)

def check_ollama_connection() -> bool:
    """Check if Ollama service is available."""
    try:
        from utils import bypass_proxy_for_ollama
        bypass_proxy_for_ollama()
        response = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_internet_connection() -> bool:
    """Check internet connectivity."""
    try:
        response = requests.get("https://httpbin.org/status/200", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_disk_space(min_gb: float = 1.0) -> bool:
    """Check available disk space."""
    try:
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024**3)
        return free_gb >= min_gb
    except:
        return False

def check_dependencies() -> Tuple[bool, Dict[str, bool]]:
    """Verify all required services are available."""
    checks = {
        'ollama': check_ollama_connection(),
        'internet': check_internet_connection(),
        'disk_space': check_disk_space()
    }
    
    all_healthy = all(checks.values())
    
    for service, status in checks.items():
        if status:
            logger.info(f"✅ {service} - OK")
        else:
            logger.warning(f"❌ {service} - FAILED")
    
    return all_healthy, checks
