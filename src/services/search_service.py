"""Web search via Tavily API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.config import get_settings
from src.services.http_client import async_client

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float | None = None


class SearchService:
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.tavily_api_key
        self.max_results = settings.search_max_results

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[SearchResult]:
        if not self.is_configured:
            logger.warning("Tavily API key not set; skipping web search.")
            return []

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": self.max_results,
            "include_answer": True,
            "search_depth": "basic",
        }

        logger.info("Searching web for: %s", query)
        async with async_client(timeout=30.0) as client:
            response = await client.post(self.BASE_URL, json=payload)
            response.raise_for_status()
            data = response.json()

        results: list[SearchResult] = []
        answer = data.get("answer")
        if answer:
            results.append(
                SearchResult(
                    title="Tavily Summary",
                    url="",
                    content=answer,
                    score=1.0,
                )
            )

        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score"),
                )
            )
        return results

    @staticmethod
    def format_results(results: list[SearchResult]) -> str:
        if not results:
            return ""

        parts: list[str] = ["Web search results:"]
        for idx, result in enumerate(results, start=1):
            header = f"{idx}. {result.title}"
            if result.url:
                header += f" ({result.url})"
            parts.append(header)
            parts.append(result.content.strip())
        return "\n".join(parts)
