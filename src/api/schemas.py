from __future__ import annotations

from pydantic import BaseModel, Field


class TextChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message text")
    session_id: str | None = Field(default=None, description="Existing session ID for context")


class TextChatResponse(BaseModel):
    session_id: str
    user_text: str
    response_text: str
    used_web_search: bool
    search_query: str | None = None
    search_results_count: int = 0
    user_language: str = "en-IN"
    response_language: str = "en-IN"


class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str
    response_text: str
    used_web_search: bool
    search_query: str | None = None
    search_results_count: int = 0
    detected_language: str | None = None
    response_language: str = "en-IN"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language_code: str | None = Field(
        default=None,
        description="Sarvam BCP-47 code (e.g. hi-IN, mr-IN, gu-IN). Auto-detected if omitted.",
    )


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, str]]


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, bool]


class PersonaResponse(BaseModel):
    name: str
    role: str
    tagline: str
    persona_id: str
    sample_greeting: str
    supported_languages: list[str]
