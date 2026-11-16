# Deployment Guide

## Pre-Deployment Checklist

### Environment Setup

1. **Create Credentials** (obtain the ones relevant to your setup)
   - GitHub token (higher rate limits, optional): https://github.com/settings/tokens
   - Gmail App Password (email delivery, optional): https://myaccount.google.com/apppasswords
   - YouTube Data API (better video search, optional): https://console.cloud.google.com/
   - LLM: Ollama (local, default) or any OpenAI-compatible key (Groq / Gemini / OpenAI)

2. **Configure Environment**
   ```bash
   cp env.example .env
   # Edit .env with the credentials above
   ```

3. **Verify `.env` is ignored**
   ```bash
   git check-ignore .env  # Should output: .env
   ```

### Pre-Deployment Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Expected: every test passes (230 at the time of writing), 0 failed, 0 skipped.
# CI (Jenkins) also fails the build below 60% line coverage of src/.

# Test the application locally
streamlit run src/app.py --server.address=0.0.0.0

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
streamlit run src/app.py --server.address=0.0.0.0

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
- `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`: Use an OpenAI-compatible cloud backend instead of Ollama (see the wiki Configuration page)
- `GITHUB_TOKEN`: For GitHub repository search
- `YOUTUBE_API_KEY`: For YouTube search
- `EMAIL_*`: For email notifications
- `RAG_MODE`, `BOOKS_RAG_URL`, `RERANK_URL`, `LOCAL_CONTEXT_MAX_CHARS`: Local knowledge (see the wiki RAG Pipeline page)

The container listens on port 7860; the compose files publish it as `8501`.

### Configuration File

All settings are centralized in `src/config.py`:
- Timeouts (web_search_timeout, llm_request_timeout, etc.)
- Content limits (max_synthesis_context_chars, max_content_preview_chars)
- File upload limits (max_file_size_mb, allowed_file_extensions), enforced in `src/uploads.py`
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
# Check Python version (need 3.12+, what the Docker image and CI use)
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
env | grep -E "OLLAMA|GITHUB"
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

Set these in `.env` (or edit the defaults in `src/config.py`):
```bash
# Adjust timeouts
WEB_SEARCH_TIMEOUT=60
LLM_REQUEST_TIMEOUT=90
```
Results per source follow the research depth (2 / 5 / 10).

## Security Best Practices

1. **Never commit .env file**
2. **Use environment-specific configs** (.env.production, .env.staging)
3. **Rotate credentials regularly**
4. **Use HTTPS in production**
5. **Implement rate limiting** at the reverse proxy (not built into the app)
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
# Option 1: Rollback Docker image (tag the working image before every rebuild)
docker tag research-agent-research-agent:latest research-agent-research-agent:pre-update   # before updating
docker compose down
docker tag research-agent-research-agent:pre-update research-agent-research-agent:latest   # to roll back
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
3. Run tests to verify functionality

## Production Checklist

- [ ] All tests passing
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
