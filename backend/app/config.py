from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_prefix="VOIT_",
        extra="ignore",
    )

    env: str = "development"
    database_url: str = "sqlite:///./voit.db"
    storage_dir: Path = Path("./storage")
    max_upload_mb: int = 2048
    allowed_origins: str = "http://localhost:5173"

    parakeet_api_key: str = Field(default="", alias="PARAKEET_API_KEY")
    parakeet_api_url: str = Field(
        default="http://localhost:9000/v1/audio/transcriptions",
        alias="PARAKEET_API_URL",
    )
    parakeet_language: str = Field(default="en-US", alias="PARAKEET_LANGUAGE")
    parakeet_model: str = Field(default="", alias="PARAKEET_MODEL")
    parakeet_retries: int = Field(default=2, alias="PARAKEET_RETRIES")
    parakeet_timeout_seconds: int = Field(default=180, alias="PARAKEET_TIMEOUT_SECONDS")
    normalized_sample_rate: int = 16000

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "audio").mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "exports").mkdir(parents=True, exist_ok=True)
    return settings
