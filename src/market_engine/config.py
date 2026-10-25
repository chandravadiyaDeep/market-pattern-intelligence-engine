"""Central configuration with safe local defaults."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read configuration from environment and optional local .env file."""

    model_config = SettingsConfigDict(env_prefix="MPIE_", env_file=".env", extra="ignore")

    database_path: str = "./data/mpie.sqlite3"
    log_level: str = "INFO"
    mode: str = "research"

    @property
    def database_file(self) -> Path:
        """Return a normalized Path for the local database."""
        return Path(self.database_path).expanduser()


settings = Settings()
