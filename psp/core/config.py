from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PSPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="PSP_", extra="ignore"
    )
    database_url: str
    api_key: str = Field(min_length=32)


settings = PSPSettings()
