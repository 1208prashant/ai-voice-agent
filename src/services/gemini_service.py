"""Gemini reasoning engine with optional tool use."""

from __future__ import annotations

import asyncio
import logging
import re

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from src.config import get_settings, load_system_prompt

logger = logging.getLogger(__name__)

SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_web",
            description=(
                "Search the internet for up-to-date technical documentation, "
                "software versions, release notes, or current best practices."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Focused search query for the technical topic.",
                    )
                },
                required=["query"],
            ),
        )
    ]
)


class GeminiQuotaError(RuntimeError):
    """Raised when all configured Gemini models hit quota limits."""


def _error_code(exc: ClientError) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def _is_rate_limit(exc: ClientError) -> bool:
    return _error_code(exc) == 429


def _retry_delay_seconds(exc: ClientError, cap: int = 30) -> int | None:
    match = re.search(r"retry in ([\d.]+)s", str(exc), re.IGNORECASE)
    if not match:
        return None
    return min(max(1, int(float(match.group(1)))), cap)


def _quota_message(error: ClientError | None) -> str:
    if error is None:
        return (
            "Gemini API quota exceeded. Wait a minute and retry, or check usage at "
            "https://aistudio.google.com/"
        )
    message = str(error)
    if "limit: 0" in message:
        return (
            "Gemini free-tier quota is unavailable for this model (limit: 0). "
            "Try GEMINI_MODEL=gemini-2.5-flash-lite in .env, wait for daily reset "
            "(midnight Pacific), or enable billing at https://aistudio.google.com/"
        )
    retry_match = re.search(r"retry in ([\d.]+)s", message, re.IGNORECASE)
    if retry_match:
        seconds = max(1, int(float(retry_match.group(1))))
        return (
            f"Gemini rate limit reached. Wait about {seconds} seconds and try again, "
            "or switch to gemini-2.5-flash-lite in .env for higher free limits."
        )
    return (
        "Gemini API quota exceeded. Wait a minute and retry, or check usage at "
        "https://aistudio.google.com/"
    )


class GeminiService:
    def __init__(self) -> None:
        settings = get_settings()
        self.models = settings.gemini_model_list
        self.temperature = settings.gemini_temperature
        self.system_prompt = load_system_prompt()
        self._client: genai.Client | None = None
        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def model(self) -> str:
        return self.models[0]

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def _build_contents(self, history: list[dict[str, str]], user_message: str) -> list[types.Content]:
        contents: list[types.Content] = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=turn["content"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
        return contents

    async def _generate_content(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        if not self._client:
            raise RuntimeError("GEMINI_API_KEY is required.")

        last_error: ClientError | None = None
        for model in self.models:
            for attempt in range(2):
                try:
                    logger.debug("Calling Gemini model: %s (attempt %d)", model, attempt + 1)
                    return await self._client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )
                except ClientError as exc:
                    if not _is_rate_limit(exc):
                        raise
                    last_error = exc
                    delay = _retry_delay_seconds(exc)
                    if attempt == 0 and delay is not None:
                        logger.warning(
                            "Gemini rate limit on %s — retrying in %ss",
                            model,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning("Gemini quota hit for model %s", model)
                    break

        raise GeminiQuotaError(_quota_message(last_error)) from last_error

    async def generate(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        search_context: str | None = None,
        enable_search_tool: bool = True,
    ) -> tuple[str, bool, str | None]:
        """
        Returns (response_text, used_search, search_query).
        """
        history = history or []
        message = user_message
        if search_context:
            message = f"{user_message}\n\n{search_context}"

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            tools=[SEARCH_TOOL] if enable_search_tool else None,
        )

        contents = self._build_contents(history, message)
        response = await self._generate_content(contents, config)

        used_search = False
        search_query: str | None = None

        if enable_search_tool and response.function_calls:
            for call in response.function_calls:
                if call.name == "search_web":
                    args = call.args or {}
                    search_query = args.get("query")
                    used_search = True
                    break
            return "", used_search, search_query

        text = (response.text or "").strip()
        if not text:
            text = "I couldn't generate a response. Please try rephrasing your question."
        return text, used_search, search_query

    async def generate_with_context(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        search_context: str | None = None,
    ) -> str:
        history = history or []
        message = user_message
        if search_context:
            message = (
                f"{user_message}\n\nUse the following web search context when answering:\n"
                f"{search_context}"
            )

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
        )
        contents = self._build_contents(history, message)
        response = await self._generate_content(contents, config)
        text = (response.text or "").strip()
        return text or "I couldn't generate a response. Please try again."

    async def should_search(self, user_message: str) -> bool:
        """Lightweight heuristic when search tool is unavailable."""
        keywords = (
            "latest",
            "current",
            "newest",
            "recent",
            "today",
            "2024",
            "2025",
            "2026",
            "version",
            "release",
            "documentation",
            "docs",
        )
        lowered = user_message.lower()
        return any(word in lowered for word in keywords)
