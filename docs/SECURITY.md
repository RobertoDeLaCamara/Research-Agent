# Security Guidelines

## Overview

This document outlines security best practices for the Research-Agent project, covering input validation, credential management, API security, and deployment considerations.

## Input Validation

### Topic Sanitization

**Implementation:** `src/validators.py`

```python
def validate_topic(topic: str) -> str:
    """Validate and sanitize research topic."""
    # Remove dangerous characters
    topic = re.sub(r'[<>"\']', '', topic)
    
    # Length limits
    if len(topic) < 3:
        raise ValueError("Topic too short")
    if len(topic) > 500:
        raise ValueError("Topic too long")
    
    return topic.strip()
```

**Protections:**
- ✅ XSS prevention (removes `<script>`, `<iframe>`)
- ✅ SQL injection prevention (parameterized queries)
- ✅ Length limits (3-500 characters)
- ✅ Special character filtering

### File Upload Security

**Restrictions:**
```python
# Allowed extensions
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md'}

# Size limit
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Path traversal prevention
safe_path = os.path.abspath(file_path)
if not safe_path.startswith(os.path.abspath(upload_dir)):
    raise ValueError("Invalid file path")
```

**Validation Function:**
```python
def validate_file_upload(filename: str, file_size: int) -> tuple[bool, str]:
    """Validate uploaded file."""
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type {ext} not allowed"
    
    # Check size
    if file_size > MAX_FILE_SIZE:
        return False, "File too large"
    
    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in '._- ')
    if not safe_name or safe_name.startswith('.'):
        return False, "Invalid filename"
    
    return True, ""
```

## Credential Management

### Environment Variables

**NEVER commit credentials to git:**

```bash
# .gitignore (verify these are present)
.env
*.key
*.pem
secrets/
*.env.local
```

**Use `.env` file:**
```bash
# .env (NEVER commit this file)
OLLAMA_BASE_URL=http://localhost:11434
TAVILY_API_KEY=your_key_here
GITHUB_TOKEN=your_token_here
EMAIL_PASSWORD=your_app_password_here
```

**Provide template:**
```bash
# env.example (commit this)
OLLAMA_BASE_URL=http://localhost:11434
TAVILY_API_KEY=your_tavily_key
GITHUB_TOKEN=your_github_token
EMAIL_PASSWORD=your_email_app_password
```

### API Key Rotation

**Best Practices:**
1. Rotate keys every 90 days
2. Use separate keys for dev/staging/prod
3. Revoke immediately if exposed
4. Monitor API usage for anomalies

**Key Sources:**
- Tavily: https://tavily.com/
- GitHub: https://github.com/settings/tokens
- Gmail App Password: https://myaccount.google.com/apppasswords
- YouTube: https://console.cloud.google.com/

### Pre-Commit Hook

**Prevent credential commits:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

if git diff --cached --name-only | grep -q "\.env$"; then
    echo "❌ Error: Attempting to commit .env file"
    exit 1
fi

if git diff --cached | grep -qE "(api_key|password|token|secret).*=.*[a-zA-Z0-9]{20,}"; then
    echo "❌ Error: Possible credential in commit"
    exit 1
fi
```

## Database Security

### SQL Injection Prevention

**Always use parameterized queries:**

```python
# ✅ CORRECT
cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))

# ❌ WRONG
cursor.execute(f'SELECT * FROM sessions WHERE id = {session_id}')
```

### Data Sanitization

```python
def save_session(topic: str, persona: str, state: dict):
    """Save session with sanitized inputs."""
    # Sanitize inputs
    topic = validate_topic(topic)
    persona = persona if persona in ALLOWED_PERSONAS else "general"
    
    # Serialize safely
    state_json = json.dumps(state, default=str)
    
    # Parameterized insert
    cursor.execute(
        'INSERT INTO sessions (topic, persona, state_json) VALUES (?, ?, ?)',
        (topic, persona, state_json)
    )
```

### Database Permissions

```bash
# Restrict database file permissions
chmod 600 research_sessions.db

# In production, use separate DB user with limited privileges
```

## API Security

### Rate Limiting (Recommended)

**Implementation with slowapi:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/minute")
def research_endpoint(request):
    """Rate-limited research endpoint."""
    # ... research logic
```

### Authentication (Future)

**Options:**
1. **API Keys**: Simple, good for service-to-service
2. **JWT Tokens**: Stateless, scalable
3. **OAuth2**: For user authentication

**Example API Key Implementation:**
```python
def verify_api_key(api_key: str) -> bool:
    """Verify API key from request header."""
    valid_keys = os.getenv("VALID_API_KEYS", "").split(",")
    return api_key in valid_keys

@app.before_request
def check_auth():
    api_key = request.headers.get("X-API-Key")
    if not verify_api_key(api_key):
        abort(401, "Invalid API key")
```

### CORS Configuration

```python
from flask_cors import CORS

# Restrict origins in production
CORS(app, origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com"
])
```

## Content Security

### Output Sanitization

**Remove potentially harmful content:**
```python
def sanitize_content(content: str, max_length: int = 50000) -> str:
    """Sanitize research content."""
    # Remove scripts
    content = re.sub(r'<script.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove javascript: URLs
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    return content.strip()
```

### LLM Prompt Injection Prevention

**Validate and sanitize user inputs before LLM:**
```python
def safe_llm_prompt(user_input: str) -> str:
    """Create safe prompt from user input."""
    # Remove prompt injection attempts
    dangerous_patterns = [
        r'ignore previous instructions',
        r'disregard.*above',
        r'new instructions:',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            raise ValueError("Invalid input detected")
    
    return user_input
```

## Deployment Security

### Docker Security

**Dockerfile best practices:**
```dockerfile
# Use specific versions, not 'latest'
FROM python:3.10-slim

# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Don't expose unnecessary ports
EXPOSE 8501

# Use secrets for sensitive data
RUN --mount=type=secret,id=env_file \
    cat /run/secrets/env_file > .env
```

**Docker Compose:**
```yaml
services:
  research-agent:
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    
    # Read-only root filesystem
    read_only: true
    
    # Drop capabilities
    cap_drop:
      - ALL
    
    # Use secrets
    secrets:
      - env_file

secrets:
  env_file:
    file: .env
```

### Network Security

**Firewall rules:**
```bash
# Allow only necessary ports
ufw allow 8501/tcp  # Streamlit
ufw allow 11434/tcp # Ollama (if external)
ufw enable
```

**Use internal networks:**
```yaml
# docker-compose.yml
networks:
  internal:
    internal: true  # No external access
  
services:
  research-agent:
    networks:
      - internal
      - default  # External access
```

### HTTPS/TLS

**Use reverse proxy (nginx):**
```nginx
server {
    listen 443 ssl http2;
    server_name research.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring & Auditing

### Security Logging

```python
import logging

security_logger = logging.getLogger('security')

def log_security_event(event_type: str, details: dict):
    """Log security-relevant events."""
    security_logger.warning(
        f"Security Event: {event_type}",
        extra={
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            **details
        }
    )

# Usage
log_security_event('invalid_input', {
    'user_ip': request.remote_addr,
    'input': sanitized_input
})
```

### Failed Authentication Tracking

```python
from collections import defaultdict
from datetime import datetime, timedelta

failed_attempts = defaultdict(list)

def check_rate_limit(ip_address: str) -> bool:
    """Check if IP has too many failed attempts."""
    now = datetime.now()
    cutoff = now - timedelta(minutes=15)
    
    # Clean old attempts
    failed_attempts[ip_address] = [
        t for t in failed_attempts[ip_address] if t > cutoff
    ]
    
    # Check limit
    if len(failed_attempts[ip_address]) >= 5:
        log_security_event('rate_limit_exceeded', {'ip': ip_address})
        return False
    
    return True
```

## Security Checklist

### Development
- [ ] Never commit `.env` files
- [ ] Use parameterized SQL queries
- [ ] Validate all user inputs
- [ ] Sanitize file uploads
- [ ] Use environment variables for secrets
- [ ] Add pre-commit hooks

### Testing
- [ ] Test XSS prevention
- [ ] Test SQL injection prevention
- [ ] Test file upload restrictions
- [ ] Test rate limiting
- [ ] Test authentication (if implemented)

### Deployment
- [ ] Use HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Set resource limits
- [ ] Run as non-root user
- [ ] Enable security logging
- [ ] Set up monitoring/alerts

### Maintenance
- [ ] Rotate API keys quarterly
- [ ] Review security logs weekly
- [ ] Update dependencies monthly
- [ ] Security audit annually
- [ ] Incident response plan documented

## Incident Response

### If Credentials Are Exposed

1. **Immediate Actions:**
   ```bash
   # Revoke exposed credentials
   # Generate new keys
   # Update .env file
   # Restart services
   ```

2. **Git History Cleanup:**
   ```bash
   # Remove from history
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   
   # Force push (if necessary)
   git push origin --force --all
   ```

3. **Notification:**
   - Notify team members
   - Check API usage logs for abuse
   - Document incident

### If Security Vulnerability Found

1. **Assess severity** (Critical/High/Medium/Low)
2. **Create private issue** (don't disclose publicly yet)
3. **Develop and test fix**
4. **Deploy fix to production**
5. **Disclose responsibly** after fix is deployed

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Docker Security](https://docs.docker.com/engine/security/)
- [LangChain Security](https://python.langchain.com/docs/security)

---

**Last Updated:** February 13, 2026
**Review Schedule:** Quarterly
