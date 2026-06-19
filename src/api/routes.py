from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from google.genai.errors import ClientError

from src import __version__
from src.api.schemas import (
    HealthResponse,
    PersonaResponse,
    SessionHistoryResponse,
    TextChatRequest,
    TextChatResponse,
    TTSRequest,
    VoiceChatResponse,
)
from src.config import get_settings
from src.persona import get_persona
from src.services.language_service import LANGUAGE_LABELS, SUPPORTED_TTS_LANGUAGES
from src.services.agent_service import AgentService
from src.services.gemini_service import GeminiQuotaError
from src.services.stt_service import STTService
from src.services.tts_service import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _handle_agent_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GeminiQuotaError):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, ClientError) and getattr(exc, "code", None) == 429:
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, RuntimeError) and not isinstance(exc, GeminiQuotaError):
        return HTTPException(status_code=503, detail=str(exc))
    logger.exception("Unhandled agent error: %s", exc)
    return HTTPException(status_code=500, detail="Unexpected server error.")


def _header_b64(text: str, max_len: int = 500) -> str:
    """Encode UTF-8 text for safe ASCII-only HTTP headers."""
    return base64.b64encode(text[:max_len].encode("utf-8")).decode("ascii")

_agent: AgentService | None = None
_stt: STTService | None = None
_tts: TTSService | None = None


def get_agent() -> AgentService:
    global _agent
    if _agent is None:
        _agent = AgentService()
    return _agent


def get_stt() -> STTService:
    global _stt
    if _stt is None:
        _stt = STTService()
    return _stt


def get_tts() -> TTSService:
    global _tts
    if _tts is None:
        _tts = TTSService()
    return _tts


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        services={
            "gemini": bool(settings.gemini_api_key),
            "web_search": bool(settings.tavily_api_key),
            "stt": bool(settings.sarvam_api_key),
            "tts": bool(settings.sarvam_api_key),
        },
    )


@router.get("/persona", response_model=PersonaResponse)
async def persona() -> PersonaResponse:
    settings = get_settings()
    p = get_persona()
    return PersonaResponse(
        name=p.name,
        role=p.role,
        tagline=p.tagline,
        persona_id=settings.assistant_persona,
        sample_greeting=p.greeting_hint(),
        supported_languages=[LANGUAGE_LABELS[code] for code in sorted(SUPPORTED_TTS_LANGUAGES)],
    )


@router.post("/chat/text", response_model=TextChatResponse)
async def chat_text(payload: TextChatRequest) -> TextChatResponse:
    agent = get_agent()
    try:
        result = await agent.chat(payload.message, session_id=payload.session_id)
    except Exception as exc:
        raise _handle_agent_error(exc) from exc

    return TextChatResponse(
        session_id=result.session_id,
        user_text=result.user_text,
        response_text=result.response_text,
        used_web_search=result.used_web_search,
        search_query=result.search_query,
        search_results_count=result.search_results_count,
        user_language=result.user_language,
        response_language=result.response_language,
    )


@router.post("/chat/voice", response_model=VoiceChatResponse)
async def chat_voice(
    audio: UploadFile = File(...),
    session_id: str | None = Query(default=None),
) -> VoiceChatResponse:
    stt = get_stt()
    agent = get_agent()

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        transcription = await stt.transcribe(audio_bytes, filename=audio.filename or "audio.wav")
        result = await agent.chat(
            transcription.text,
            session_id=session_id,
            user_language=transcription.language_code,
        )
    except Exception as exc:
        raise _handle_agent_error(exc) from exc

    return VoiceChatResponse(
        session_id=result.session_id,
        transcript=transcription.text,
        response_text=result.response_text,
        used_web_search=result.used_web_search,
        search_query=result.search_query,
        search_results_count=result.search_results_count,
        detected_language=transcription.language_code,
        response_language=result.response_language,
    )


@router.post("/chat/voice/full")
async def chat_voice_full(
    audio: UploadFile = File(...),
    session_id: str | None = Query(default=None),
) -> Response:
    """Voice chat that returns spoken audio with transcript in headers."""
    stt = get_stt()
    tts = get_tts()
    agent = get_agent()

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        transcription = await stt.transcribe(audio_bytes, filename=audio.filename or "audio.wav")
        result = await agent.chat(
            transcription.text,
            session_id=session_id,
            user_language=transcription.language_code,
        )
        speech = await tts.synthesize(
            result.response_text,
            language_code=result.response_language,
        )
    except Exception as exc:
        http_exc = _handle_agent_error(exc)
        if http_exc.status_code != 500:
            raise http_exc from exc
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise

    headers = {
        "X-Session-Id": result.session_id,
        "X-Metadata-Encoded": "base64",
        "X-Transcript": _header_b64(transcription.text),
        "X-Response-Text": _header_b64(result.response_text),
        "X-Used-Web-Search": str(result.used_web_search).lower(),
    }
    if result.search_query:
        headers["X-Search-Query"] = _header_b64(result.search_query, max_len=200)

    return Response(content=speech, media_type=tts.media_type, headers=headers)


@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)) -> dict[str, str]:
    stt = get_stt()
    audio_bytes = await audio.read()
    try:
        transcription = await stt.transcribe(audio_bytes, filename=audio.filename or "audio.wav")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "text": transcription.text,
        "language_code": transcription.language_code,
    }


@router.post("/tts")
async def text_to_speech(payload: TTSRequest) -> Response:
    tts = get_tts()
    try:
        audio = await tts.synthesize(payload.text, language_code=payload.language_code)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type=tts.media_type)


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def session_history(session_id: str) -> SessionHistoryResponse:
    agent = get_agent()
    messages = await agent.get_history(session_id)
    return SessionHistoryResponse(session_id=session_id, messages=messages)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    agent = get_agent()
    await agent.reset_session(session_id)
    return {"status": "cleared", "session_id": session_id}
