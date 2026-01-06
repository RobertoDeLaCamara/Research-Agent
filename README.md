# Research-Agent 🔬

An autonomous research agent powered by LangChain and LangGraph that performs deep investigation into any topic using multiple sources and generates professional reports.

## 🌟 Key Features

*   **Multi-Source Research**: Investigations across Wikipedia, Google Search (Tavily), arXiv, Semantic Scholar, GitHub, and YouTube.
*   **AI Synthesis**: Uses advanced LLMs to consolidate findings into a technical Executive Summary.
*   **Professional Reporting**:
    *   **HTML Report**: Full-featured report with truncated research sections for better readability and full bibliography.
    *   **PDF Summary**: High-quality PDF focused exclusively on the Executive Summary for professional sharing.
*   **Smart Linking**: Automatic extraction of URLs with clickable links in the summary and bibliography.
*   **Email Delivery**: Automatically sends the generated reports (HTML + PDF) to your email via SMTP.
*   **Local-First Architecture**: Designed to work with local models like Qwen 2.5/Gemma via Ollama.

## 🛠 Architecture

The agent follows a graph-based workflow using **LangGraph**:

1.  **Wikipedia**: Initial context gathering.
2.  **Web Search**: Current events and diverse viewpoints.
3.  **Scientific Repositories**: arXiv and Semantic Scholar for academic depth.
4.  **GitHub**: Real-world implementations and code.
5.  **YouTube**: Expert explanations and audiovisual context.
6.  **Synthesis**: LLM-driven consolidation of all data.
7.  **Reporting**: Final HTML/PDF generation and email dispatch.

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   [Ollama](https://ollama.com/) with `qwen2.5:14b` (or your preferred model)
*   API Keys for Tavily, Semantic Scholar (optional), and GitHub.

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
    TAVILY_API_KEY=your_key
    GITHUB_TOKEN=your_token
    EMAIL_USER=your_email
    EMAIL_PASS=your_app_password
    ```

### Usage

Run the agent with a research topic:
```bash
python src/main.py "Your research topic here"
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
