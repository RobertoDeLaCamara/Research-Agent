import hashlib
import json
import os
import time
from functools import wraps
from typing import Any, Optional
from config import settings

CACHE_DIR = "cache"

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(topic: str, source: str = "") -> str:
    """Generate cache key from topic and source."""
    content = f"{topic}_{source}".lower()
    return hashlib.md5(content.encode()).hexdigest()

def get_from_cache(cache_key: str) -> Optional[dict]:
    """Retrieve data from cache if not expired."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if not os.path.exists(cache_file):
        return None
        
    try:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
            
        # Check if expired
        if time.time() - cached_data['timestamp'] > settings.cache_expiry_hours * 3600:
            os.remove(cache_file)
            return None
            
        return cached_data
    except:
        return None

def save_to_cache(cache_key: str, data: Any):
    """Save data to cache with timestamp."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    cached_data = {
        'timestamp': time.time(),
        'data': data
    }
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(cached_data, f)
    except:
        pass  # Fail silently if cache write fails

def cache_research(source: str = ""):
    """Decorator to cache research results."""
    def decorator(func):
        @wraps(func)
        def wrapper(state_or_topic, *args, **kwargs):
            # Extract topic from state or use directly
            topic = state_or_topic.get("topic") if isinstance(state_or_topic, dict) else str(state_or_topic)
            
            cache_key = get_cache_key(topic, source)
            cached = get_from_cache(cache_key)
            
            if cached:
                return cached['data']
                
            result = func(state_or_topic, *args, **kwargs)
            save_to_cache(cache_key, result)
            return result
        return wrapper
    return decorator
