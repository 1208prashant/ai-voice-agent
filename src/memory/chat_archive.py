"""Persist conversation transcripts to timestamped files on disk."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.memory.session_store import SessionStore, StoredMessage

logger = logging.getLogger(__name__)


class ChatArchive:
    """Writes each session's full transcript to data/chats/ (configurable)."""

    def __init__(self, session_store: SessionStore | None = None) -> None:
        settings = get_settings()
        self.enabled = settings.chat_archive_enabled
        self.archive_dir = settings.chat_archive_full_path
        self._sessions = session_store

    @property
    def sessions(self) -> SessionStore:
        if self._sessions is None:
            from src.memory.session_store import SessionStore

            self._sessions = SessionStore()
        return self._sessions

    def init(self) -> None:
        if self.enabled:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    @staticmethod
    def _format_timestamp(ts: str) -> str:
        return ChatArchive._parse_iso(ts).strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _filename_timestamp(ts: str) -> str:
        """Filesystem-safe stamp from session start time."""
        dt = ChatArchive._parse_iso(ts)
        return dt.strftime("%Y-%m-%d_%H%M%S")

    def _base_name(self, session_id: str, started_at: str) -> str:
        short_id = session_id.split("-")[0]
        return f"{self._filename_timestamp(started_at)}_{short_id}"

    def text_path(self, session_id: str, started_at: str) -> Path:
        return self.archive_dir / f"{self._base_name(session_id, started_at)}.txt"

    def json_path(self, session_id: str, started_at: str) -> Path:
        return self.archive_dir / f"{self._base_name(session_id, started_at)}.json"

    def _format_text_transcript(
        self,
        session_id: str,
        started_at: str,
        updated_at: str,
        messages: list[StoredMessage],
    ) -> str:
        settings = get_settings()
        lines = [
            "VoiceOps AI Assistant — Chat Transcript",
            "=" * 48,
            f"Session ID   : {session_id}",
            f"Started      : {self._format_timestamp(started_at)}",
            f"Last updated : {self._format_timestamp(updated_at)}",
            f"Persona      : {settings.assistant_persona}",
            f"Messages     : {len(messages)}",
            "",
            "-" * 48,
            "",
        ]

        for msg in messages:
            role_label = "USER" if msg.role == "user" else "ASSISTANT"
            lang = ""
            if msg.metadata and msg.metadata.get("language"):
                lang = f" [{msg.metadata['language']}]"
            search_note = ""
            if msg.metadata and msg.metadata.get("used_web_search"):
                query = msg.metadata.get("search_query") or ""
                search_note = f" (web search: {query})" if query else " (web search)"

            lines.append(f"[{self._format_timestamp(msg.created_at)}] {role_label}{lang}{search_note}")
            lines.append(msg.content)
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _format_json_export(
        self,
        session_id: str,
        started_at: str,
        updated_at: str,
        messages: list[StoredMessage],
    ) -> dict[str, Any]:
        settings = get_settings()
        return {
            "session_id": session_id,
            "started_at": started_at,
            "updated_at": updated_at,
            "persona": settings.assistant_persona,
            "message_count": len(messages),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at,
                    "metadata": msg.metadata or {},
                }
                for msg in messages
            ],
        }

    async def save_session(self, session_id: str) -> Path | None:
        """Rewrite transcript files for a session (text + JSON)."""
        if not self.enabled:
            return None

        info = await self.sessions.get_session_info(session_id)
        if not info:
            return None

        messages = await self.sessions.get_all_messages(session_id)
        if not messages:
            return None

        started_at = info["created_at"]
        updated_at = info["updated_at"]
        text_path = self.text_path(session_id, started_at)
        json_path = self.json_path(session_id, started_at)

        text_body = self._format_text_transcript(session_id, started_at, updated_at, messages)
        json_body = json.dumps(
            self._format_json_export(session_id, started_at, updated_at, messages),
            ensure_ascii=False,
            indent=2,
        )

        await asyncio.to_thread(text_path.write_text, text_body, encoding="utf-8")
        await asyncio.to_thread(json_path.write_text, json_body + "\n", encoding="utf-8")

        logger.debug("Chat archived to %s", text_path.name)
        return text_path
