import threading
import logging
from contextlib import contextmanager
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

@contextmanager
def safe_thread_execution(timeout: int = 30):
    """Context manager for safe thread execution with timeout."""
    result = {"data": None, "error": None}
    thread = None
    
    def wrapper(func: Callable, *args, **kwargs):
        try:
            result["data"] = func(*args, **kwargs)
        except Exception as e:
            result["error"] = e
            logger.error(f"Thread execution failed: {e}")
    
    try:
        yield result, wrapper
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning(f"Thread timed out after {timeout} seconds")
                result["error"] = TimeoutError(f"Operation timed out after {timeout}s")
    finally:
        # Cleanup resources if needed
        pass

def execute_with_timeout(func: Callable, timeout: int = 30, *args, **kwargs) -> Optional[Any]:
    """Execute function with timeout using safe threading."""
    with safe_thread_execution(timeout) as (result, wrapper):
        thread = threading.Thread(target=wrapper, args=(func,) + args, kwargs=kwargs)
        thread.start()
    
    if result["error"]:
        if isinstance(result["error"], TimeoutError):
            logger.warning(f"Function {func.__name__} timed out")
        else:
            logger.error(f"Function {func.__name__} failed: {result['error']}")
        return None
    
    return result["data"]
