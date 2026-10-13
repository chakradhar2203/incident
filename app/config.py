"""
RCA Assistant – Application Settings
Reads configuration from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── ServiceNow ────────────────────────────────────────────
    servicenow_instance_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""
    servicenow_writeback_enabled: bool = False

    # ── Claude / Anthropic ────────────────────────────────────
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"

    # ── Firebase ──────────────────────────────────────────────
    firebase_service_account_path: str = "firebase-service-account.json"
    firebase_project_id: str = ""

    # ── Application ───────────────────────────────────────────
    analysis_mode: str = "ai"   # "local" | "ai" (always AI mode by default)
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    scheduler_interval_minutes: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()

