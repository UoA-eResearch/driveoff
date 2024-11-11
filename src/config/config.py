from pydantic import BaseSettings, Field
import os

class Settings(BaseSettings):
    environment: str = Field(default="development", env="ENVIRONMENT")
    api_key: str = Field(default="dummy_dev_key", env="API_KEY")
    debug: bool = Field(default=False, env="DEBUG_MODE")

    class Config:
        # Load environment-specific .env file based on the `environment` setting
        env_file = ".env.development" if os.getenv("ENVIRONMENT") == "development" else ".env" # Specify path to .env file for easy loading

settings = Settings()  # Instantiate a global config object for easy import