import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ProgressTracker:
    def __init__(self, total_steps: int, callback: Optional[Callable] = None):
        self.total = total_steps
        self.current = 0
        self.callback = callback
        self.steps = []
        
    def update(self, step_name: str):
        """Update progress and log current step."""
        self.current += 1
        progress = (self.current / self.total) * 100
        self.steps.append(step_name)
        
        logger.info(f"Progress: {progress:.1f}% - {step_name}")
        
        if self.callback:
            self.callback(progress, step_name)
            
    def get_progress(self) -> dict:
        """Get current progress information."""
        return {
            'current': self.current,
            'total': self.total,
            'percentage': (self.current / self.total) * 100,
            'steps_completed': self.steps
        }

# Global progress tracker instance
_progress_tracker: Optional[ProgressTracker] = None

def init_progress(total_steps: int, callback: Optional[Callable] = None):
    """Initialize global progress tracker."""
    global _progress_tracker
    _progress_tracker = ProgressTracker(total_steps, callback)

def update_progress(step_name: str):
    """Update global progress tracker."""
    if _progress_tracker:
        _progress_tracker.update(step_name)

def get_progress() -> dict:
    """Get current progress."""
    if _progress_tracker:
        return _progress_tracker.get_progress()
    return {'current': 0, 'total': 0, 'percentage': 0, 'steps_completed': []}
