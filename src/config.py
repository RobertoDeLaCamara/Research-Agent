from pydantic_settings import BaseSettings
from typing import Optional

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
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
