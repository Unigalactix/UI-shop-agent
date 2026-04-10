"""
config/settings.py
──────────────────
Centralised application settings loaded from environment variables (and an
optional .env file via python-dotenv).

All configuration lives here so that the rest of the codebase never calls
`os.getenv` directly; instead it imports `settings` from this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (shopping-agent/) if it exists.
# Callers that have already loaded the environment don't get overridden.
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


class Settings:
    """Typed, single-source-of-truth for all runtime configuration."""

    # ── LLM ──────────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")   # "openai" | "anthropic"
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # ── Walmart ───────────────────────────────────────────────────────────────
    WALMART_EMAIL: str = os.getenv("WALMART_EMAIL", "")
    WALMART_PASSWORD: str = os.getenv("WALMART_PASSWORD", "")
    WALMART_BASE_URL: str = "https://www.walmart.com"

    # ── Browser ───────────────────────────────────────────────────────────────
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    BROWSER_SLOW_MO: int = int(os.getenv("BROWSER_SLOW_MO", "300"))
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30000"))

    # ── MCP Server ────────────────────────────────────────────────────────────
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8765"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def validate(self) -> None:
        """Raise ValueError if required credentials are missing."""
        missing: list[str] = []

        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        if not self.WALMART_EMAIL:
            missing.append("WALMART_EMAIL")
        if not self.WALMART_PASSWORD:
            missing.append("WALMART_PASSWORD")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please copy .env.example to .env and fill in the values."
            )


# Module-level singleton – import this everywhere.
settings = Settings()
