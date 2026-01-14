import re
from typing import Literal
from pydantic import BaseModel, validator, Field

class ResearchRequest(BaseModel):
    """Validated research request."""
    topic: str = Field(..., min_length=3, max_length=500)
    research_depth: Literal["quick", "standard", "deep"] = "standard"
    persona: Literal["general", "business", "tech", "academic", "pm", "news_editor"] = "general"
    
    @validator('topic')
    def validate_topic_field(cls, v):
        """Prevent injection attacks."""
        if not v or not v.strip():
            raise ValueError("Topic cannot be empty")
        
        forbidden = ['<script>', 'javascript:', 'onerror=', '<?php', '<iframe>']
        v_lower = v.lower()
        if any(f in v_lower for f in forbidden):
            raise ValueError("Invalid characters in topic")
        
        return v.strip()

def validate_topic(topic: str) -> str:
    """Validate and clean research topic."""
    if not topic:
        raise ValueError("Topic cannot be empty")
        
    topic = topic.strip()
    
    if len(topic) < 3:
        raise ValueError("Topic must be at least 3 characters long")
        
    if len(topic) > 500:
        raise ValueError("Topic too long (maximum 500 characters)")
        
    # Remove potentially harmful characters
    topic = re.sub(r'[<>"\']', '', topic)
    
    return topic

def validate_email(email: str) -> bool:
    """Basic email validation."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def sanitize_content(content: str, max_length: int = 50000) -> str:
    """Sanitize and truncate content."""
    if not content:
        return ""
        
    # Remove potentially harmful content
    content = re.sub(r'<script.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "..."
        
    return content.strip()

def validate_file_upload(filename: str, file_size: int, max_size: int = 10485760) -> tuple[bool, str]:
    """Validate uploaded file.
    
    Args:
        filename: Name of the uploaded file
        file_size: Size in bytes
        max_size: Maximum allowed size in bytes (default 10MB)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    import os
    
    # Allowed extensions
    allowed_extensions = {'.pdf', '.txt', '.md'}
    
    # Check extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in allowed_extensions:
        return False, f"File type {ext} not allowed. Allowed: {', '.join(allowed_extensions)}"
    
    # Check size
    if file_size > max_size:
        return False, f"File too large: {file_size / 1024 / 1024:.1f}MB (max {max_size / 1024 / 1024:.0f}MB)"
    
    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in '._- ')
    if not safe_name or safe_name.startswith('.'):
        return False, "Invalid filename"
    
    return True, ""
