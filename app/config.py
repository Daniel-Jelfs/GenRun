from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Supabase
    supabase_url: str
    supabase_key: str
    
    # Discord
    discord_webhook_url: str
    
    # Google Gemini AI
    gemini_api_key: Optional[str] = None
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    cron_hour: int = 6
    cron_minute: int = 0
    
    # Scraping
    request_delay: int = 3
    max_retries: int = 3
    timeout: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
