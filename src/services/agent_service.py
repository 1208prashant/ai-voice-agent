"""Orchestrates conversation flow, tools, and context."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import get_settings
from src.memory.session_store import SessionStore
from src.services.gemini_service import GeminiService
from src.services.language_service import detect_explicit_language_request, language_instruction, resolve_language
from src.services.search_service import SearchService

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    session_id: str
    user_text: str
    response_text: str
    used_web_search: bool = False
    search_query: str | None = None
    search_results_count: int = 0
    user_language: str = "en-IN"
    response_language: str = "en-IN"
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentService:
    def __init__(
        self,
        session_store: SessionStore | None = None,
        gemini: GeminiService | None = None,
        search: SearchService | None = None,
    ) -> None:
        self.sessions = session_store or SessionStore()
        self.gemini = gemini or GeminiService()
        self.search = search or SearchService()
        self.default_language = get_settings().default_language_code

    async def init(self) -> None:
        await self.sessions.init()
        await self.sessions.purge_expired()

    async def chat(
        self,
        user_text: str,
        session_id: str | None = None,
        user_language: str | None = None,
    ) -> AgentResponse:
        sid = await self.sessions.create_session(session_id)
        history_messages = await self.sessions.get_history(sid)
        history = [{"role": m.role, "content": m.content} for m in history_messages]

        session_language = self._language_from_history(history_messages)
        active_language = resolve_language(
            user_text,
            detected=user_language,
            session_language=session_language,
            fallback=self.default_language,
        )

        model_input = self._prepare_user_message(user_text, history, active_language)

        used_search = False
        search_query: str | None = None
        search_results_count = 0
        search_context = ""

        response_text, requested_search, query = await self.gemini.generate(
            model_input,
            history=history,
            enable_search_tool=self.search.is_configured,
        )

        if requested_search and query:
            used_search = True
            search_query = query
            results = await self.search.search(query)
            search_results_count = len(results)
            search_context = self.search.format_results(results)
            response_text = await self.gemini.generate_with_context(
                model_input,
                history=history,
                search_context=search_context,
            )
        elif not response_text and self.search.is_configured:
            if await self.gemini.should_search(user_text):
                used_search = True
                search_query = user_text
                results = await self.search.search(user_text)
                search_results_count = len(results)
                search_context = self.search.format_results(results)
                response_text = await self.gemini.generate_with_context(
                    model_input,
                    history=history,
                    search_context=search_context,
                )

        if not response_text:
            response_text, _, _ = await self.gemini.generate(
                model_input,
                history=history,
                enable_search_tool=False,
            )

        response_language = active_language

        await self.sessions.add_message(
            sid,
            "user",
            user_text,
            metadata={"language": active_language},
        )
        await self.sessions.add_message(
            sid,
            "assistant",
            response_text,
            metadata={
                "used_web_search": used_search,
                "search_query": search_query,
                "language": response_language,
            },
        )

        logger.info(
            "Session %s | lang=%s | search=%s | response_len=%d",
            sid[:8],
            response_language,
            used_search,
            len(response_text),
        )

        return AgentResponse(
            session_id=sid,
            user_text=user_text,
            response_text=response_text,
            used_web_search=used_search,
            search_query=search_query,
            search_results_count=search_results_count,
            user_language=active_language,
            response_language=response_language,
        )

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        messages = await self.sessions.get_history(session_id)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def reset_session(self, session_id: str) -> None:
        await self.sessions.clear_session(session_id)

    @staticmethod
    def _language_from_history(messages) -> str | None:
        for message in reversed(messages):
            if message.role != "user":
                continue
            if message.metadata and message.metadata.get("language"):
                return message.metadata["language"]
        return None

    @staticmethod
    def _prepare_user_message(
        user_text: str,
        history: list[dict[str, str]],
        language_code: str,
    ) -> str:
        lang_hint = language_instruction(language_code)
        explicit_lang_request = detect_explicit_language_request(user_text) is not None

        if not history:
            prefix = (
                "[New voice session — greet briefly with your name, then help naturally. "
                f"{lang_hint}]\n\n"
            )
            return f"{prefix}User said: {user_text}"

        if explicit_lang_request or not history or language_code != "en-IN":
            return f"[{lang_hint}]\n\n{user_text}"
        return user_text
