import re

def validate_topic(topic: str) -> str:
    """Validate and clean research topic."""
    if not topic:
        raise ValueError("Topic cannot be empty")
        
    topic = topic.strip()
    
    if len(topic) < 3:
        raise ValueError("Topic must be at least 3 characters long")
        
    if len(topic) > 200:
        raise ValueError("Topic too long (maximum 200 characters)")
        
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
