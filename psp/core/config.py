from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PSPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="PSP_", extra="ignore"
    )
    database_url: str
    api_key: str = Field(min_length=32)
    payflow_webhook_secret: str = Field(min_length=32)
    payflow_base_url: str = "http://127.0.0.1:8000"
    payflow_timeout_seconds: float = Field(default=5.0, gt=0)
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = Field(default=3600, gt=0)
    celery_broker_url: str = "redis://localhost:6379/1"

settings = PSPSettings()
