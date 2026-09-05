"""Application settings, loaded from environment / .env (12-factor)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENTINEL_",
        extra="ignore",
    )

    app_name: str = "Sentinel"
    # Default to a local SQLite file so the app runs with zero infra.
    # Production swaps this for a Postgres URL via the env var — nothing else changes.
    database_url: str = "sqlite:///./sentinel.db"
    # Used from M2 onward (the Claude risk scorer).
    anthropic_api_key: str | None = None


settings = Settings()
