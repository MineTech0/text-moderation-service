from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Service Info
    SERVICE_NAME: str = "Text Moderation Service"
    DEBUG: bool = True
    
    # Model Configuration
    MODEL_BACKEND: str = "huggingface_pipeline"
    MODEL_NAME: str = "TurkuNLP/bert-large-finnish-cased-toxicity"
    MODEL_DEVICE: int = -1 # CPU
    
    # Wordlist Configuration
    WORDLIST_DIR: str = "./data"
    WORDLIST_FI_URL: str = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/fi"
    WORDLIST_EN_URL: str = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en"
    WORDLIST_REFRESH_DAYS: int = 7
    
    # Moderation Thresholds
    TRIVIAL_LENGTH_THRESHOLD: int = 2
    BLOCK_THRESHOLD: float = 0.9
    FLAG_THRESHOLD: float = 0.7
    
    # Worker Configuration
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 1.5

    # Auth (Placeholder)
    API_TOKEN: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()

