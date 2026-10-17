# Installation

## Option A — Docker with a local model (no API keys)

Starts Ollama and pulls a small model automatically.

```bash
git clone https://github.com/RobertoDeLaCamara/Research-Agent
cd Research-Agent
docker compose -f docker-compose.full.yml up
```

The first run downloads `qwen2.5:1.5b` (about 1 GB); later starts reuse it. Open **http://localhost:8501**.

For a larger model, change `OLLAMA_MODEL` and the `ollama pull` line in `docker-compose.full.yml` (the model name appears in both places).

## Option B — Free cloud API (Groq, Gemini)

No local GPU or Ollama needed.

```bash
git clone https://github.com/RobertoDeLaCamara/Research-Agent
cd Research-Agent
cp env.example .env
```

Edit `.env`:

```env
# Groq — free tier, no credit card
OPENAI_API_KEY="gsk_..."                          # console.groq.com
OLLAMA_BASE_URL="https://api.groq.com/openai/v1"
OLLAMA_MODEL="llama-3.1-8b-instant"
```

Then `docker compose up` and open **http://localhost:8501**.

## Option C — Manual setup (no Docker)

**Prerequisites:** Python 3.12 (what the Docker image and CI use), and either [Ollama](https://ollama.com) or a cloud API key.

```bash
git clone https://github.com/RobertoDeLaCamara/Research-Agent
cd Research-Agent

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp env.example .env               # edit with your settings
streamlit run src/app.py
```

The CLI works too: `python src/main.py "Your topic" --depth standard --persona general`.

## Optional API keys

All are optional; the agent degrades gracefully without them.

| Variable | Purpose |
|----------|---------|
| `TAVILY_API_KEY` | Better web search (free tier available) |
| `GITHUB_TOKEN` | Higher GitHub API rate limits |
| `YOUTUBE_API_KEY` | Enables the YouTube transcript source |

See [Configuration](Configuration.md) for every setting.
