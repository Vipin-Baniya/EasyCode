"""
Configuration management for Project Core.
All settings loaded from environment variables / .env file.
"""

from __future__ import annotations

from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings – loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Project Core"
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # API server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)
    api_reload: bool = Field(default=True)

    # Security
    secret_key: str = Field(default="changeme-in-production-32chars-min")
    jwt_secret: str = Field(default="changeme-jwt-secret-32chars-min")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)

    # Database
    database_url: str = Field(default="sqlite:///./projectcore.db")
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=10)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # CORS – stored as comma-separated string in env; parsed to list
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return []

    # Frontend
    frontend_url: str = Field(default="http://localhost:3000")

    # LLM – correct current model ID
    anthropic_api_key: str = Field(default="")
    llm_model: str = Field(default="claude-sonnet-4-20250514")
    llm_max_tokens: int = Field(default=8192)
    llm_temperature: float = Field(default=0.7)
    llm_rate_limit_requests: int = Field(default=100)
    llm_rate_limit_period: int = Field(default=60)
    llm_max_context_messages: int = Field(default=50)

    # Execution
    enable_code_execution: bool = Field(default=True)
    sandbox_timeout: int = Field(default=300)
    max_execution_time: int = Field(default=600)

    # File system
    workspace_root: str = Field(default="./workspaces")
    max_file_size: int = Field(default=10_485_760)

    allowed_file_extensions: list[str] = Field(
        default=[".py", ".js", ".ts", ".tsx", ".jsx", ".json",
                 ".md", ".txt", ".yml", ".yaml", ".toml", ".sql",
                 ".sh", ".html", ".css", ".scss"],
    )

    @field_validator("allowed_file_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return []

    # Security settings
    default_permission_level: str = Field(default="review")
    require_approval_for_destructive: bool = Field(default=True)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)
    session_timeout: int = Field(default=3600)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_file: str | None = Field(default=None)

    # Monitoring
    sentry_dsn: str | None = Field(default=None)
    sentry_environment: str = Field(default="development")
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)

    # Testing
    test_database_url: str | None = Field(default=None)
    run_integration_tests: bool = Field(default=True)
    test_timeout: int = Field(default=300)
    mock_llm: bool = Field(default=False)
    mock_execution: bool = Field(default=False)

    # Feature flags
    feature_multi_repo: bool = Field(default=True)
    feature_advanced_refactor: bool = Field(default=True)
    feature_collaborative: bool = Field(default=False)
    feature_websocket_updates: bool = Field(default=True)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def effective_cors_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        if self.is_production:
            origins.append("https://*.vercel.app")
            if self.frontend_url not in origins:
                origins.append(self.frontend_url)
        return origins


settings = Settings()


def get_settings() -> Settings:
    return settings
