"""Module for reading configuration files."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file() -> list[Path]:
    """Given the mode this app should run in, return the dotenv files
    that should be used. If no file matching mode exists, raises a ValueError.

    Returns:
        list[Path]: The list of dotenv files.
    """
    mode = "development"
    if "MODE" in os.environ:
        mode = os.environ["MODE"]
    mode_dir = Path("modes")
    all_env_files = [mode_dir / f".env.{mode}", mode_dir / f".env.{mode}.local"]
    files_that_exist = [file for file in all_env_files if file.is_file()]
    if len(files_that_exist) == 0:
        raise ValueError("No matching dotenv file exists for specified mode.")
    return files_that_exist


class Settings(BaseSettings):
    """
    Configurations for Driveoff. Use get_settings() for a cached version of the settings.
    For secrets use `SecretStr` so they are not accidentally logged.
    """

    cors_allow_host: list[str] = []
    activescale_hostname: str = ""
    activescale_region: str = ""
    activescale_access_key: SecretStr | None = None
    activescale_secret_key: SecretStr | None = None
    log_level: str = "INFO"
    projectdb_base_url: str = ""
    projectdb_api_key: str = ""

    model_config = SettingsConfigDict(env_file=get_env_file(), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Returns a cached version of the Settings."""
    return Settings()
