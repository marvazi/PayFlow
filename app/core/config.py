from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    database_url: str
    jwt_secret_key: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    cache_ttl_seconds: int = Field(default=3600, gt=0)
    psp_base_url: str = "http://127.0.0.1:8001"
    psp_api_key: str
    psp_timeout_seconds: float = Field(default=5.0, gt=0)


settings = Settings()
