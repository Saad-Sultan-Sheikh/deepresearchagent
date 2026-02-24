"""Pydantic Settings — loads .env, typed config for the entire application."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM API Keys ──────────────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    google_api_key: str = Field(..., description="Google Gemini API key")

    # ── Search API Keys ───────────────────────────────────────────────────────
    tavily_api_key: str = Field(..., description="Tavily search API key")
    brave_api_key: str = Field(..., description="Brave search API key")
    exa_api_key: str = Field(..., description="Exa AI search API key")

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    # Set NEO4J_ENABLED=false to skip graph persistence entirely (no Neo4j needed)
    neo4j_enabled: bool = Field(default=True)
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="", description="Neo4j password")

    # ── LangSmith ─────────────────────────────────────────────────────────────
    langchain_tracing_v2: str = Field(default="true")
    langchain_api_key: Optional[str] = Field(default=None)
    langchain_project: str = Field(default="deep-research-agent")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com")

    # ── Agent settings ────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    reports_dir: Path = Field(default=Path("reports"))
    logs_dir: Path = Field(default=Path("logs"))
    max_search_results_per_query: int = Field(default=10)
    search_timeout_seconds: int = Field(default=30)
    llm_temperature: float = Field(default=0.1)
    max_concurrent_searches: int = Field(default=5)

    # ── Model names ───────────────────────────────────────────────────────────
    analyzer_model: str = Field(default="claude-sonnet-4-6")
    extractor_model: str = Field(default="gemini-2.5-flash")

    @field_validator("reports_dir", "logs_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
