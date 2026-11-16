from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    # AI Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"

    # API Keys
    github_token: Optional[str] = None
    youtube_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Email Configuration
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipient: Optional[str] = None

    # Timeout Configuration
    web_search_timeout: int = 12
    llm_request_timeout: int = 60
    content_fetch_timeout: int = 3
    
    # Content Limits
    max_synthesis_context_chars: int = 25000
    # Budget for the local knowledge (RAG / books) section of that context. Local chunks go first and
    # the context is cut from the end, so without a cap 8 book chunks (~12-15k chars) pushed web and
    # arXiv sources out of the window. Whole chunks are kept until the budget is used; 0 = no cap.
    local_context_max_chars: int = 7500
    # Ollama context window for the synthesis call. Must fit the system prompt
    # + up to max_synthesis_context_chars of sources (~8k tokens) + num_predict
    # output; otherwise Ollama silently drops the *start* of the prompt (the
    # instructions) and the model just echoes raw source text.
    synthesis_num_ctx: int = 16384
    max_content_preview_chars: int = 5000
    
    # File Upload Limits
    max_file_size_mb: int = 10
    # Only what local_rag can read (rag_tools / rag_index handle .pdf and .txt)
    allowed_file_extensions: List[str] = ['.pdf', '.txt']
    
    # Database Configuration
    db_path: str = "research_sessions.db"
    
    # Research Keywords
    research_trigger_keywords: List[str] = [
        "investiga", "busca", "más información",
        "research", "search", "investigate"
    ]
    
    # Logging
    log_level: str = "INFO"

    # extra="ignore": .env also carries variables that are read straight from
    # os.environ (RAG_MODE, RERANK_URL, LIGHT_LLM_*). Rejecting them would make
    # importing this module fail for anyone following env.example.
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
