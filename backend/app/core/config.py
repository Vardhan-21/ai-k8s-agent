"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenRouter AI Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "minimax/minimax-m3.1-flash:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_MAX_RETRIES: int = 1

    # Kubernetes Configuration
    KUBECONFIG_PATH: str = ""

    # InsForge Configuration
    INSFORGE_BASE_URL: str = "https://wen6ngih.us-east.insforge.app"
    INSFORGE_API_KEY: str = "ik_eeb0831044c203497ac6e8783f0d5461"
    INSFORGE_ANON_KEY: str = "anon_72e00885ca16e42bbed0182e83cf911642dd814b6b8340cd39452c6bec2ffbad"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
