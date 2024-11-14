import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings"""
    # No ENVIRONMENT variable, assuming 'production' by default
    api_key: str = Field(..., env="API_KEY")  # Required
    api_url: str = Field(..., env="API_URL")  # Required
    debug: bool = Field(False, env="DEBUG_MODE")  # Optional, defaults to False

    class Config:
        env_file = os.path.join("..", f".env")  # Loads .env from the parent directory

settings = Settings()  # Instantiate a global config object for easy import
print(settings.dict())
