from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # AI Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    
    # API Keys
    tavily_api_key: Optional[str] = None
    github_token: Optional[str] = None
    youtube_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Email Configuration
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipient: Optional[str] = None
    
    # Performance Settings
    max_results_per_source: int = 5
    max_concurrent_requests: int = 5
    max_content_length: int = 50000
    request_timeout: int = 30
    cache_expiry_hours: int = 24
    
    # Timeout Configuration
    web_search_timeout: int = 45
    llm_request_timeout: int = 60
    content_fetch_timeout: int = 3
    thread_execution_timeout: int = 30
    
    # Content Limits
    max_synthesis_context_chars: int = 25000
    max_content_preview_chars: int = 5000
    
    # File Upload Limits
    max_file_size_mb: int = 10
    allowed_file_extensions: List[str] = ['.pdf', '.txt', '.md']
    
    # Research Keywords
    research_trigger_keywords: List[str] = [
        "investiga", "busca", "más información",
        "research", "search", "investigate"
    ]
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
