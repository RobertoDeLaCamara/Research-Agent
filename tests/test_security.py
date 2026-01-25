
import pytest
from src.validators import validate_topic, validate_file_upload, ResearchRequest, sanitize_content
from pydantic import ValidationError

def test_validate_topic_clean_success():
    """Test standard valid topics."""
    assert validate_topic("Machine Learning") == "Machine Learning"
    assert validate_topic("  Data Science  ") == "Data Science"
    assert validate_topic("123 Testing") == "123 Testing"

def test_validate_topic_xss_prevention():
    """Test that potential XSS payloads are rejected or cleaned."""
    # Test strict validation via pydantic model
    with pytest.raises(ValueError, match="Invalid characters"):
        ResearchRequest(topic="<script>alert(1)</script>")
        
    with pytest.raises(ValueError, match="Invalid characters"):
        ResearchRequest(topic="javascript:void(0)")

    # Test cleaning function
    assert validate_topic("Test <script> removal") == "Test script removal"
    assert validate_topic("Test 'quotes'") == "Test quotes"

def test_validate_topic_length():
    """Test length constraints."""
    with pytest.raises(ValueError):
        validate_topic("") # Empty
        
    with pytest.raises(ValueError):
        validate_topic("ab") # Too short
        
    long_topic = "a" * 501
    with pytest.raises(ValueError, match="Topic too long"):
        validate_topic(long_topic)

def test_validate_file_upload_extensions():
    """Test file extension whitelisting."""
    valid, _ = validate_file_upload("test.pdf", 1000)
    assert valid is True
    
    valid, _ = validate_file_upload("test.txt", 1000)
    assert valid is True
    
    valid, msg = validate_file_upload("test.exe", 1000)
    assert valid is False
    assert "File type .exe not allowed" in msg
    
    valid, msg = validate_file_upload("script.sh", 1000)
    assert valid is False

def test_validate_file_upload_size():
    """Test file size limits."""
    # Custom max size: 1MB
    limit = 1024 * 1024
    valid, _ = validate_file_upload("large.pdf", limit - 1, max_size=limit)
    assert valid is True
    
    valid, msg = validate_file_upload("too_large.pdf", limit + 1, max_size=limit)
    assert valid is False
    assert "File too large" in msg

def test_validate_file_upload_filename_sanitization():
    """Test filename sanitization."""
    # Path traversal attempt
    valid, msg = validate_file_upload("../../../etc/passwd.txt", 1000)
    assert valid is False # Should fail validation or just be treated as invalid name
    
    # In validate_file_upload implementation:
    # `_, ext = os.path.splitext(filename)` might keep path components
    # But `safe_name` logic checks it.
    
    # If the function is robust, it should handle this.
    # Reading validators.py again:
    # safe_name = "".join(c for c in filename if c.isalnum() or c in '._- ')
    # if not safe_name or safe_name.startswith('.'): return False
    
    # "../" would become ".." which starts with . -> False. Good.
    pass

def test_sanitize_content():
    """Test html/script cleanup in content."""
    dirty = "Hello <script>bad()</script> world"
    clean = sanitize_content(dirty)
    assert "bad()" not in clean
    assert clean == "Hello  world"
    
    dirty_js = "javascript:alert(1)"
    clean = sanitize_content(dirty_js)
    assert "alert(1)" in clean # it removes javascript: prefix
    assert "javascript:" not in clean
