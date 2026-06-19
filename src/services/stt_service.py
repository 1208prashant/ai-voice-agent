"""Speech-to-text via Sarvam AI."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import get_settings
from src.services.http_client import async_client
from src.services.language_service import normalize_language_code

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    language_code: str | None = None


class STTService:
    BASE_URL = "https://api.sarvam.ai/speech-to-text"
    SUPPORTED_EXTENSIONS = {
        ".wav",
        ".mp3",
        ".m4a",
        ".webm",
        ".ogg",
        ".opus",
        ".flac",
        ".mp4",
        ".aac",
        ".aiff",
        ".amr",
        ".wma",
    }
    MAX_RETRIES = 3

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.sarvam_api_key
        self.model = settings.sarvam_stt_model
        self.language_code = settings.sarvam_stt_language_code
        self.mode = settings.sarvam_stt_mode

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _guess_content_type(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".wav"
        guessed, _ = mimetypes.guess_type(f"file{suffix}")
        return guessed or "application/octet-stream"

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> TranscriptionResult:
        if not self.is_configured:
            raise RuntimeError("SARVAM_API_KEY is required for speech-to-text.")

        if not audio_bytes:
            raise RuntimeError("Empty audio recording. Hold the talk button and speak clearly.")

        suffix = Path(filename).suffix.lower() or ".wav"
        if suffix not in self.SUPPORTED_EXTENSIONS:
            filename = "upload.wav"
            suffix = ".wav"
        content_type = self._guess_content_type(filename)

        form_data: dict[str, str] = {"model": self.model}
        stt_language = normalize_language_code(self.language_code)
        if stt_language:
            form_data["language_code"] = stt_language
        else:
            form_data["language_code"] = "unknown"
        if self.model == "saaras:v3" and self.mode:
            form_data["mode"] = self.mode

        logger.info(
            "Transcribing audio with Sarvam (%d bytes, %s)",
            len(audio_bytes),
            Path(filename).name,
        )

        last_error: Exception | None = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with async_client(timeout=90.0) as client:
                    response = await client.post(
                        self.BASE_URL,
                        headers={"api-subscription-key": self.api_key},
                        files={"file": (Path(filename).name, audio_bytes, content_type)},
                        data=form_data,
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:300]
                raise RuntimeError(
                    f"Sarvam STT request failed ({exc.response.status_code}): {detail}"
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Sarvam STT connection attempt %d/%d failed: %s",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(attempt)
        else:
            raise RuntimeError(
                "Could not connect to Sarvam AI for speech-to-text. "
                "Check your internet connection and try again."
            ) from last_error

        transcript = (data.get("transcript") or "").strip()
        if not transcript:
            raise RuntimeError(
                "No speech detected. Hold the talk button, speak clearly, and try again."
            )

        detected_lang = normalize_language_code(data.get("language_code"))
        if not detected_lang:
            logger.warning(
                "Sarvam STT did not return language_code; session/default will be used."
            )
        logger.info(
            "Transcription (%s): %s",
            detected_lang or "unknown",
            transcript[:120],
        )
        return TranscriptionResult(text=transcript, language_code=detected_lang)
