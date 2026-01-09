import time
import logging
from collections import defaultdict
from functools import wraps
from typing import Dict, List

logger = logging.getLogger(__name__)

class Metrics:
    def __init__(self):
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.errors: Dict[str, int] = defaultdict(int)
        
    def time_operation(self, operation_name: str):
        """Decorator to time operations."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.counters[f"{operation_name}_success"] += 1
                    return result
                except Exception as e:
                    self.errors[operation_name] += 1
                    self.counters[f"{operation_name}_error"] += 1
                    raise
                finally:
                    duration = time.time() - start
                    self.timings[operation_name].append(duration)
            return wrapper
        return decorator
    
    def increment(self, counter_name: str):
        """Increment a counter."""
        self.counters[counter_name] += 1
        
    def get_stats(self) -> Dict:
        """Get performance statistics."""
        stats = {
            'counters': dict(self.counters),
            'errors': dict(self.errors),
            'timings': {}
        }
        
        for operation, times in self.timings.items():
            if times:
                stats['timings'][operation] = {
                    'count': len(times),
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'total': sum(times)
                }
        
        return stats
    
    def log_stats(self):
        """Log current statistics."""
        stats = self.get_stats()
        
        for operation, timing in stats['timings'].items():
            logger.info(f"{operation}: {timing['count']} calls, avg {timing['avg']:.2f}s")
            
        if stats['errors']:
            logger.warning(f"Errors: {stats['errors']}")

# Global metrics instance
metrics = Metrics()
