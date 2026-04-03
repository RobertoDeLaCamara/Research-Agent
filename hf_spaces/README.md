---
title: Research Agent
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: LangGraph research agent — 10 sources, RAG, Streamlit
tags:
  - langchain
  - langgraph
  - rag
  - research
  - streamlit
  - agent
  - multi-source
  - nlp
  - llm
  - groq
  - ollama
  - arxiv
  - wikipedia
license: mit
---

# 🔍 Research-Agent

> Give it a topic. Get a sourced, structured research report in minutes.

**Research-Agent** is an autonomous LangGraph agent that searches **10 sources in parallel**, detects knowledge gaps and re-plans automatically, then exports a cited report in PDF, Word, Markdown, or HTML.

## ✨ Features

- **10 parallel sources** — Web (Tavily), Wikipedia, arXiv, Semantic Scholar, GitHub, Hacker News, Stack Overflow, Reddit, YouTube, local RAG
- **Self-correction loop** — evaluates gaps and re-plans up to 2 iterations
- **5 research personas** — Generalist, Software Architect, Market Analyst, Scientific Reviewer, Product Manager
- **Export** — PDF, Word, Markdown, HTML with citations
- **Cloud LLM support** — Groq (free), Gemini (free), OpenAI, or any OpenAI-compatible API
- **Bilingual UI** — English / Spanish toggle

## 🚀 Getting started

1. **Get a free API key** from [Groq](https://console.groq.com) — takes 2 min, no credit card
2. Paste it in the sidebar **LLM API Key** panel → click **Apply**
3. Optionally add a [Tavily](https://tavily.com) key for web search (free tier: 1000 req/month)
4. Type a research topic and click **Start Research**

## 🔑 API keys

| Key | Source | Required? |
|---|---|---|
| LLM (Groq / Gemini / OpenAI) | sidebar | ✅ Yes |
| Tavily | sidebar | Optional (web search) |
| GitHub Token | sidebar | Optional (GitHub source) |
| YouTube Data API | sidebar | Optional (better YT search) |

Wikipedia, arXiv, Hacker News, Stack Overflow, Reddit and Semantic Scholar work **without any key**.

## 🛠️ Self-host

```bash
git clone https://github.com/RobertoDeLaCamara/Research-Agent
cd Research-Agent
docker compose -f docker-compose.full.yml up   # batteries included (Ollama + qwen2.5:1.5b)
```

## 📄 Source code

[github.com/RobertoDeLaCamara/Research-Agent](https://github.com/RobertoDeLaCamara/Research-Agent)
