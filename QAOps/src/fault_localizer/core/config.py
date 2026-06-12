import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Settings:
    """Centralized configuration and environment variable management."""
    
    # GitHub Integration
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    
    # Model Providers
    MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "google")
    MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
    
    # API Keys
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

settings = Settings()
