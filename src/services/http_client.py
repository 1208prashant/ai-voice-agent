"""Shared HTTP client settings for external API calls."""

from __future__ import annotations

import ssl

import certifi
import httpx


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def async_client(timeout: float = 60.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=30.0),
        verify=ssl_context(),
        http2=False,
    )
