"""Text-to-speech via Sarvam AI Bulbul."""

from __future__ import annotations

import base64
import io
import logging
import re
import wave
from dataclasses import dataclass

import httpx

from src.config import get_settings
from src.services.http_client import async_client
from src.services.language_service import detect_script_language, normalize_language_code
from src.services.speech_formatter import prepare_for_speech

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    audio: bytes
    media_type: str = "audio/wav"


class TTSService:
    BASE_URL = "https://api.sarvam.ai/text-to-speech"
    MAX_CHARS = 2500

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.sarvam_api_key
        self.speaker = settings.sarvam_speaker
        self.model = settings.sarvam_model
        self.language_code = settings.sarvam_language_code
        self.sample_rate = settings.sarvam_sample_rate
        self.output_codec = settings.sarvam_output_codec
        self.pace = settings.sarvam_pace
        self.temperature = settings.sarvam_temperature
        self.default_language = settings.default_language_code

    @property
    def media_type(self) -> str:
        if self.output_codec == "mp3":
            return "audio/mpeg"
        return "audio/wav"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _split_text(self, text: str) -> list[str]:
        text = text.strip()
        if len(text) <= self.MAX_CHARS:
            return [text]

        chunks: list[str] = []
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if not sentence:
                continue
            if len(sentence) > self.MAX_CHARS:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for i in range(0, len(sentence), self.MAX_CHARS):
                    chunks.append(sentence[i : i + self.MAX_CHARS])
                continue
            if len(current) + len(sentence) + 1 > self.MAX_CHARS:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current.strip())
        return chunks or [text[: self.MAX_CHARS]]

    async def _synthesize_chunk(self, text: str, language_code: str) -> bytes:
        spoken_text = prepare_for_speech(text)
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": spoken_text,
            "target_language_code": language_code,
            "speaker": self.speaker,
            "model": self.model,
            "speech_sample_rate": self.sample_rate,
            "output_audio_codec": self.output_codec,
            "pace": self.pace,
            "temperature": self.temperature,
        }

        async with async_client(timeout=60.0) as client:
            response = await client.post(self.BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        audios = data.get("audios") or []
        if not audios:
            raise RuntimeError("Sarvam TTS returned no audio.")

        return base64.b64decode(audios[0])

    @staticmethod
    def _concat_wav(chunks: list[bytes]) -> bytes:
        if len(chunks) == 1:
            return chunks[0]

        output = io.BytesIO()
        writer: wave.Wave_write | None = None
        for chunk in chunks:
            with wave.open(io.BytesIO(chunk), "rb") as reader:
                if writer is None:
                    writer = wave.open(output, "wb")
                    writer.setparams(reader.getparams())
                writer.writeframes(reader.readframes(reader.getnframes()))
        if writer is not None:
            writer.close()
        return output.getvalue()

    def _resolve_tts_language(self, language_code: str | None, text: str = "") -> str:
        """Use Sarvam/session language; script-only fallback for typed text (no keyword guessing)."""
        explicit = normalize_language_code(language_code)
        if explicit:
            return explicit
        configured = normalize_language_code(self.language_code)
        if configured:
            return configured
        script_lang = detect_script_language(text)
        if script_lang:
            return script_lang
        return self.default_language

    async def synthesize(self, text: str, language_code: str | None = None) -> bytes:
        if not self.is_configured:
            raise RuntimeError("SARVAM_API_KEY is required for text-to-speech.")

        tts_language = self._resolve_tts_language(language_code, text)
        chunks = self._split_text(text)
        logger.info(
            "Synthesizing speech with Sarvam (%d chars, %s, %d chunk(s))",
            len(text),
            tts_language,
            len(chunks),
        )

        audio_parts: list[bytes] = []
        for chunk in chunks:
            audio_parts.append(await self._synthesize_chunk(chunk, tts_language))

        if self.output_codec == "wav" and len(audio_parts) > 1:
            return self._concat_wav(audio_parts)
        return b"".join(audio_parts)

    async def synthesize_result(self, text: str, language_code: str | None = None) -> TTSResult:
        return TTSResult(
            audio=await self.synthesize(text, language_code=language_code),
            media_type=self.media_type,
        )
