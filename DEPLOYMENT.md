# Deployment Guide

## Pre-Deployment Checklist

### 🔴 Critical Security Tasks

Before deploying to production, you **MUST** complete these security tasks:

1. **Revoke Exposed Credentials**
   - The `.env` file contains exposed API keys that must be revoked immediately
   - Revoke: TAVILY_API_KEY, GITHUB_TOKEN, EMAIL_PASSWORD, YOUTUBE_API_KEY

2. **Generate New Credentials**
   - Tavily: https://tavily.com/
   - GitHub: https://github.com/settings/tokens
   - Gmail App Password: https://myaccount.google.com/apppasswords
   - YouTube: https://console.cloud.google.com/

3. **Update Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your NEW credentials
   ```

4. **Verify .env is in .gitignore**
   ```bash
   git check-ignore .env  # Should output: .env
   ```

### ✅ Pre-Deployment Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Verify all 37 tests pass
# Expected: 37 passed, 0 failed, 0 skipped

# Test the application locally
streamlit run src/app.py

# Test Docker build
docker compose build

# Test Docker run
docker compose up -d
docker compose logs -f
```

## Deployment Options

### Option 1: Docker Compose (Recommended)

```bash
# 1. Build the image
docker compose build

# 2. Start services
docker compose up -d

# 3. Check logs
docker compose logs -f research-agent

# 4. Access at http://localhost:8501
```

### Option 2: Local Python

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run application
streamlit run src/app.py

# 4. Access at http://localhost:8501
```

### Option 3: Production Server

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run with production settings
streamlit run src/app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true

# 3. Use a process manager (systemd, supervisor, pm2)
```

## Configuration

### Environment Variables

Required:
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use (default: qwen3:14b)

Optional:
- `TAVILY_API_KEY`: For web search
- `GITHUB_TOKEN`: For GitHub repository search
- `YOUTUBE_API_KEY`: For YouTube search
- `EMAIL_*`: For email notifications

### Configuration File

All settings are centralized in `src/config.py`:
- Timeouts (web_search_timeout, llm_request_timeout, etc.)
- Content limits (max_synthesis_context_chars, max_content_preview_chars)
- File upload limits (max_file_size_mb, allowed_file_extensions)
- Research keywords

## Monitoring

### Health Checks

```bash
# Check if application is running
curl http://localhost:8501/_stcore/health

# Check Ollama connection
curl http://localhost:11434/api/tags

# Check database
sqlite3 research_sessions.db "SELECT COUNT(*) FROM sessions;"
```

### Logs

```bash
# Docker logs
docker compose logs -f

# Application logs (if configured)
tail -f logs/research-agent.log
```

## Troubleshooting

### Tests Failing

```bash
# Check Python version (need 3.10+)
python3 --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check for import errors
python3 -c "from src.agent import app; print('OK')"
```

### Application Not Starting

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check port is available
lsof -i :8501

# Check environment variables
env | grep -E "OLLAMA|TAVILY"
```

### Docker Issues

```bash
# Rebuild without cache
docker compose build --no-cache

# Check container logs
docker compose logs research-agent

# Restart services
docker compose restart
```

## Scaling

### Horizontal Scaling

For multiple instances:
1. Use external database (PostgreSQL instead of SQLite)
2. Use Redis for caching
3. Use load balancer (nginx, HAProxy)
4. Share knowledge_base directory via NFS or S3

### Performance Tuning

In `src/config.py`:
```python
# Increase concurrent requests
max_concurrent_requests: int = 10

# Adjust timeouts
web_search_timeout: int = 60
llm_request_timeout: int = 90

# Increase cache expiry
cache_expiry_hours: int = 48
```

## Security Best Practices

1. **Never commit .env file**
2. **Use environment-specific configs** (.env.production, .env.staging)
3. **Rotate credentials regularly**
4. **Use HTTPS in production**
5. **Implement rate limiting** (see ACTION_ITEMS.md)
6. **Regular security audits**
   ```bash
   bandit -r src/
   ```

## Backup and Recovery

### Database Backup

```bash
# Backup SQLite database
cp research_sessions.db research_sessions.db.backup

# Automated backup (cron)
0 2 * * * cp /path/to/research_sessions.db /path/to/backups/research_sessions_$(date +\%Y\%m\%d).db
```

### Knowledge Base Backup

```bash
# Backup uploaded files
tar -czf knowledge_base_backup.tar.gz knowledge_base/
```

## Rollback Plan

If issues occur after deployment:

```bash
# Option 1: Rollback Docker image
docker compose down
docker compose up -d --force-recreate

# Option 2: Restore from backup
cp research_sessions.db.backup research_sessions.db

# Option 3: Revert git commit
git revert <commit-hash>
git push origin main
```

## Support

For issues:
1. Check logs first
2. Review CHANGELOG.md for recent changes
3. Check CODE_REVIEW.md for known issues
4. Run tests to verify functionality

## Production Checklist

- [ ] All tests passing (37/37)
- [ ] Exposed credentials revoked
- [ ] New credentials generated and configured
- [ ] .env file not in git
- [ ] Docker build successful
- [ ] Application starts without errors
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rollback plan documented
- [ ] Security scan clean (`bandit -r src/`)
