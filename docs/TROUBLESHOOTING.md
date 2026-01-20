# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### Problem: `pip install` fails with dependency conflicts

**Solution:**
```bash
# Use fresh virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Problem: `ModuleNotFoundError: No module named 'docx'`

**Solution:**
```bash
pip install python-docx PyPDF2
```

### Ollama Connection Issues

#### Problem: `Connection refused` to Ollama

**Symptoms:**
```
Error: Cannot connect to Ollama at http://localhost:11434
```

**Solutions:**

1. **Check if Ollama is running:**
```bash
# Check process
ps aux | grep ollama

# Check port
lsof -i :11434
```

2. **Start Ollama:**
```bash
# macOS/Linux
ollama serve

# Docker
docker run -d -p 11434:11434 ollama/ollama
```

3. **Verify connection:**
```bash
curl http://localhost:11434/api/tags
```

4. **Check environment variable:**
```bash
# In .env file
OLLAMA_BASE_URL=http://localhost:11434

# Or set directly
export OLLAMA_BASE_URL=http://localhost:11434
```

#### Problem: Model not found

**Symptoms:**
```
Error: model 'qwen3:14b' not found
```

**Solution:**
```bash
# Pull the model
ollama pull qwen3:14b

# List available models
ollama list

# Use alternative model
# Update .env: OLLAMA_MODEL=llama3:8b
```

### Test Failures

#### Problem: All tests fail with import errors

**Symptoms:**
```
ImportError: cannot import name 'search_web_node' from 'src.tools.research_tools'
```

**Solution:**
```bash
# Ensure correct import structure
# Check that src/__init__.py exists
touch src/__init__.py
touch src/tools/__init__.py

# Run tests with proper path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

#### Problem: Tests timeout

**Symptoms:**
```
Test hangs and never completes
```

**Solution:**
```bash
# Increase timeout in pytest
pytest tests/ -v --timeout=300

# Or reduce timeout in config.py
# web_search_timeout: int = 30  # Reduce from 45
```

### API Issues

#### Problem: Tavily API key invalid

**Symptoms:**
```
Error: Invalid API key for Tavily
```

**Solution:**
1. Get new API key from https://tavily.com/
2. Update `.env` file:
```bash
TAVILY_API_KEY=your_new_key_here
```
3. Restart application

#### Problem: GitHub API rate limit exceeded

**Symptoms:**
```
Error: API rate limit exceeded for GitHub
```

**Solution:**
```bash
# Add GitHub token to .env
GITHUB_TOKEN=your_github_token

# Generate token at: https://github.com/settings/tokens
# Required scopes: public_repo (read-only)
```

### Research Issues

#### Problem: Research hangs or times out

**Symptoms:**
- UI becomes unresponsive
- No results after several minutes

**Solutions:**

1. **Check timeout settings:**
```python
# src/config.py
web_search_timeout: int = 45  # Increase if needed
thread_execution_timeout: int = 30
```

2. **Reduce research depth:**
```python
# Use "quick" instead of "deep"
research_depth = "quick"  # 2 results per source
```

3. **Disable slow sources:**
```python
# In UI, uncheck slow sources like YouTube
```

4. **Check network connectivity:**
```bash
# Test external APIs
curl https://api.tavily.com/
curl https://api.github.com/
```

#### Problem: Empty or poor quality results

**Symptoms:**
- Research completes but results are minimal
- Report is very short

**Solutions:**

1. **Check API keys are configured:**
```bash
# Verify .env file has keys
cat .env | grep API_KEY
```

2. **Enable more sources:**
```python
# In UI, enable multiple sources:
# ✓ Web, Wiki, arXiv, Scholar, GitHub, etc.
```

3. **Increase research depth:**
```python
research_depth = "deep"  # 10 results per source
```

4. **Check logs for errors:**
```bash
# Look for API failures
tail -f logs/research.log
```

### Database Issues

#### Problem: Database locked

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Close all connections
pkill -f research-agent

# Remove lock file
rm research_sessions.db-journal

# Restart application
```

#### Problem: Cannot load previous sessions

**Symptoms:**
- History shows no sessions
- Load session fails

**Solution:**
```bash
# Check database exists
ls -lh research_sessions.db

# Verify database integrity
sqlite3 research_sessions.db "PRAGMA integrity_check;"

# If corrupted, reinitialize
rm research_sessions.db
# Restart app (will recreate)
```

### File Upload Issues

#### Problem: File upload rejected

**Symptoms:**
```
Error: File type .docx not allowed
```

**Solution:**
```python
# Only these extensions allowed:
# .pdf, .txt, .md

# Convert your file:
# .docx → .txt (copy/paste content)
# .doc → .pdf (print to PDF)
```

#### Problem: File too large

**Symptoms:**
```
Error: File too large: 15.2MB (max 10MB)
```

**Solution:**
1. **Split large files:**
```bash
# Split PDF
pdftk large.pdf cat 1-50 output part1.pdf
pdftk large.pdf cat 51-100 output part2.pdf
```

2. **Or increase limit in config:**
```python
# src/config.py
max_file_size_mb: int = 20  # Increase from 10
```

### Docker Issues

#### Problem: Docker container won't start

**Symptoms:**
```
Error: Cannot start container research-agent
```

**Solution:**
```bash
# Check logs
docker logs research-agent

# Rebuild image
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check port conflicts
lsof -i :8501
```

#### Problem: Cannot connect to Ollama from Docker

**Symptoms:**
```
Error: Connection refused to http://localhost:11434
```

**Solution:**
```yaml
# docker-compose.yml
services:
  research-agent:
    environment:
      # Use host.docker.internal on Mac/Windows
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      
      # Or use Docker network
      OLLAMA_BASE_URL: http://ollama:11434
  
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
```

### Performance Issues

#### Problem: Research is very slow

**Symptoms:**
- Takes 5+ minutes to complete
- UI is sluggish

**Solutions:**

1. **Use faster model:**
```bash
# .env
OLLAMA_MODEL=llama3:8b  # Faster than qwen3:14b
```

2. **Reduce sources:**
```python
# Disable slow sources in UI:
# ✗ YouTube (slow transcript fetching)
# ✗ Reddit (rate limited)
```

3. **Enable caching:**
```python
# Caching is enabled by default
# Check cache directory exists
ls -lh cache/
```

4. **Increase timeouts:**
```python
# src/config.py
web_search_timeout: int = 60  # From 45
```

### Memory Issues

#### Problem: Out of memory errors

**Symptoms:**
```
MemoryError: Unable to allocate array
```

**Solution:**
```python
# Reduce content limits in config.py
max_synthesis_context_chars: int = 15000  # From 25000
max_content_preview_chars: int = 3000     # From 5000
```

### Export Issues

#### Problem: PDF generation fails

**Symptoms:**
```
Error: Cannot generate PDF report
```

**Solution:**
```bash
# Install PDF dependencies
pip install fpdf2

# Check report content isn't too large
# Try exporting as Markdown first
```

#### Problem: Word export has formatting issues

**Symptoms:**
- Missing sections
- Broken formatting

**Solution:**
```bash
# Reinstall python-docx
pip install --upgrade python-docx

# Try alternative export format (HTML/Markdown)
```

## Debugging Tips

### Enable Debug Logging

```python
# src/config.py
log_level: str = "DEBUG"  # From "INFO"
```

### Check Logs

```bash
# View recent logs
tail -f logs/research.log

# Search for errors
grep ERROR logs/research.log

# Filter by component
grep "research_tools" logs/research.log
```

### Test Individual Components

```python
# Test web search only
from src.tools.research_tools import search_web_node

state = {"topic": "test", "research_depth": "quick", "queries": {}}
result = search_web_node(state)
print(result)
```

### Verify Environment

```bash
# Check Python version
python --version  # Should be 3.10+

# Check installed packages
pip list | grep -E "langchain|ollama|streamlit"

# Check environment variables
env | grep -E "OLLAMA|TAVILY|GITHUB"
```

## Getting Help

### Before Asking for Help

1. **Check this guide** for your specific issue
2. **Review logs** for error messages
3. **Test with minimal example** to isolate problem
4. **Check GitHub issues** for similar problems

### Reporting Issues

Include this information:

```markdown
**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.10.12]
- Ollama Model: [e.g., qwen3:14b]

**Issue:**
[Clear description of the problem]

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Logs:**
```
[Paste relevant logs]
```

**Configuration:**
[Relevant .env settings, with API keys redacted]
```

### Useful Commands

```bash
# System info
uname -a
python --version
pip list

# Check services
ps aux | grep ollama
lsof -i :8501
lsof -i :11434

# Test connectivity
curl http://localhost:11434/api/tags
curl https://api.tavily.com/

# Clean restart
pkill -f streamlit
pkill -f ollama
rm -rf cache/
rm research_sessions.db
# Restart services
```

## Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Import errors | `export PYTHONPATH="${PYTHONPATH}:$(pwd)"` |
| Ollama not found | `ollama serve` |
| Tests fail | `pip install python-docx PyPDF2` |
| Slow research | Use `research_depth="quick"` |
| Database locked | `rm research_sessions.db-journal` |
| Port in use | `lsof -i :8501` then kill process |
| Cache issues | `rm -rf cache/` |
| Memory errors | Reduce `max_synthesis_context_chars` |

---

**Last Updated:** January 20, 2026  
**Need more help?** Check GitHub Issues or create a new issue with details above.
