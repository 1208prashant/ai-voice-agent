"""Session memory backed by SQLite."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

from src.config import get_settings


@dataclass
class Message:
    role: str
    content: str
    metadata: dict[str, Any] | None = None


@dataclass
class StoredMessage:
    role: str
    content: str
    created_at: str
    metadata: dict[str, Any] | None = None


class SessionStore:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = str(db_path or settings.session_db_full_path)
        self.ttl_hours = settings.session_ttl_hours
        self.max_turns = settings.max_history_turns

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)"
            )
            await db.commit()

    async def create_session(self, session_id: str | None = None) -> str:
        sid = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (sid, now, now),
            )
            await db.commit()
        return sid

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata) if metadata else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, meta_json, now),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            await db.commit()

    async def _fetch_messages(self, session_id: str) -> list[StoredMessage]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT role, content, metadata, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()

        messages: list[StoredMessage] = []
        for row in rows:
            meta = json.loads(row["metadata"]) if row["metadata"] else None
            messages.append(
                StoredMessage(
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                    metadata=meta,
                )
            )
        return messages

    async def get_session_info(self, session_id: str) -> dict[str, str] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT session_id, created_at, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def get_all_messages(self, session_id: str) -> list[StoredMessage]:
        """Full message history for archival (not trimmed to max_history_turns)."""
        return await self._fetch_messages(session_id)

    async def get_history(self, session_id: str) -> list[Message]:
        messages = await self._fetch_messages(session_id)
        trimmed = [
            Message(role=m.role, content=m.content, metadata=m.metadata) for m in messages
        ]
        if len(trimmed) > self.max_turns * 2:
            trimmed = trimmed[-(self.max_turns * 2) :]
        return trimmed

    async def clear_session(self, session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    async def purge_expired(self) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT session_id FROM sessions WHERE updated_at < ?", (cutoff,)
            )
            expired = [row[0] for row in await cursor.fetchall()]
            for sid in expired:
                await db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
                await db.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
            await db.commit()
        return len(expired)
