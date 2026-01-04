"""
Configuration settings for the Text Moderation Service.

All settings can be overridden via environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # -------------------------------------------------------------------------
    # Service Info
    # -------------------------------------------------------------------------
    SERVICE_NAME: str = "Text Moderation Service"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "text"
    
    # -------------------------------------------------------------------------
    # Model Configuration
    # -------------------------------------------------------------------------
    MODEL_BACKEND: str = "huggingface_pipeline"
    MODEL_NAME: str = "TurkuNLP/bert-large-finnish-cased-toxicity"
    MODEL_DEVICE: int = -1  # -1 for CPU, 0+ for GPU
    
    # -------------------------------------------------------------------------
    # Wordlist Configuration
    # -------------------------------------------------------------------------
    WORDLIST_DIR: str = "./data"
    WORDLIST_FI_URL: str = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/fi"
    WORDLIST_EN_URL: str = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en"
    WORDLIST_REFRESH_DAYS: int = 7
    
    # -------------------------------------------------------------------------
    # Moderation Thresholds
    # -------------------------------------------------------------------------
    TRIVIAL_LENGTH_THRESHOLD: int = 2
    BLOCK_THRESHOLD: float = 0.9
    FLAG_THRESHOLD: float = 0.7
    
    # -------------------------------------------------------------------------
    # Worker Configuration
    # -------------------------------------------------------------------------
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 1.5
    CALLBACK_TIMEOUT: int = 10

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    API_TOKEN: Optional[str] = None
    CORS_ORIGINS: str = "*"  # Comma-separated origins or "*"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # -------------------------------------------------------------------------
    # Server Settings
    # -------------------------------------------------------------------------
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000
    UVICORN_WORKERS: int = 1
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG


settings = Settings()
