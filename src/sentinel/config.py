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
    # Path to the declarative policy file (M1).
    policy_path: str = "policy.yaml"

    # --- Risk engine (M2) ---
    # Which LLM backs the contextual risk scorer:
    #   "auto"  -> gemini if a key is set, else anthropic if set, else mock
    #   "mock" | "gemini" | "anthropic" -> force that provider
    risk_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Approvals (M3) --- optional Slack webhook for human-in-the-loop notices.
    slack_webhook_url: str | None = None

    # --- Dashboard (M5) ---
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    eval_results_path: str = "eval/results.json"
    # If this dir exists (the built dashboard), the API serves it at "/".
    static_dir: str = "dashboard/dist"


settings = Settings()
