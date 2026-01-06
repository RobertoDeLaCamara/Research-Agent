# Research-Agent 🔬

An autonomous research agent powered by LangChain and LangGraph that performs deep investigation into any topic using multiple sources and generates professional reports.

## 🌟 Key Features

*   **Multi-Source Research**: Investigations across Wikipedia, Google Search (Tavily), arXiv, Semantic Scholar, GitHub, and YouTube.
*   **Robust Content Extraction**:
    *   **YouTube Fallback**: Automatically continues research using video metadata (titles/authors) if transcripts are blocked or unavailable.
    *   **GitHub Recall**: Intelligent search fallback that broadens the scope if specific language-filtered results are not found.
*   **Bilingual Support**: Dynamic language detection (English/Spanish) for Wikipedia sources based on the research topic.
*   **Premium Reporting**:
    *   **Modern HTML Report**: High-end aesthetic with a clean, card-based mobile-responsive design and professional typography.
    *   **PDF Summary**: High-quality PDF focused on the Executive Summary for professional sharing.
*   **AI Synthesis**: Uses advanced LLMs (Ollama-based Qwen 2.5/Gemma) to consolidate findings into a technical Executive Summary.
*   **Email Delivery**: Automatically sends the generated reports (HTML + PDF) to your email via SMTP.

## 🛠 Architecture

The agent follows a graph-based workflow using **LangGraph**:

1.  **Wikipedia**: Initial context gathering with auto-language detection.
2.  **Web Search**: Current events via Tavily (with DuckDuckGo fallback).
3.  **Scientific Repositories**: arXiv and Semantic Scholar for academic depth.
4.  **GitHub**: Broadened search for implementations and code.
5.  **YouTube**: Analysis with transcript/metadata extraction.
6.  **Synthesis**: LLM-driven consolidation of all data.
7.  **Reporting**: Premium HTML/PDF generation and email dispatch.

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   [Ollama](https://ollama.com/) with `qwen2.5:14b` (recommended) or any preferred model.
*   API Keys for **Tavily** and **GitHub** (Token).

### Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/robcamgar/Research-Agent.git
    cd Research-Agent
    ```

2.  **Install dependencies**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure environment**:
    Copy `env.example` to `.env` and fill in your credentials:
    ```bash
    cp env.example .env
    # Edit .env with your keys
    ```

### Usage

Run the agent with a research topic:
```bash
python src/main.py "Your research topic here"
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
