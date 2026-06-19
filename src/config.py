from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "src" / "prompts"
DATA_DIR = ROOT_DIR / "data"

load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_fallback_models: str = "gemini-2.5-flash,gemini-1.5-flash"
    gemini_temperature: float = 0.65

    assistant_persona: str = "dev-mentor"
    assistant_name: str = ""

    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saarika:v2.5"
    sarvam_stt_language_code: str = "unknown"
    sarvam_stt_mode: str = "transcribe"
    sarvam_speaker: str = "rohan"
    sarvam_model: str = "bulbul:v3"
    sarvam_language_code: str = "auto"
    sarvam_sample_rate: int = 24000
    sarvam_output_codec: str = "wav"
    sarvam_pace: float = 0.92
    sarvam_temperature: float = 0.72
    default_language_code: str = "en-IN"

    tavily_api_key: str = ""
    search_max_results: int = 5

    session_db_path: str = "data/sessions.db"
    session_ttl_hours: int = 24
    max_history_turns: int = 20

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    cors_origins: str = "*"

    @property
    def gemini_model_list(self) -> list[str]:
        models: list[str] = []
        for candidate in [self.gemini_model, *self.gemini_fallback_models.split(",")]:
            name = candidate.strip()
            if name and name not in models:
                models.append(name)
        return models

    @property
    def session_db_full_path(self) -> Path:
        path = Path(self.session_db_path)
        if not path.is_absolute():
            path = ROOT_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_system_prompt() -> str:
    from src.persona import get_persona

    return get_persona().build_system_prompt()
