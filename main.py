"""VoiceOps AI Assistant — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import __version__
from src.api.routes import get_agent, router
from src.config import ROOT_DIR, get_settings

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting VoiceOps AI Assistant v%s", __version__)
    agent = get_agent()
    await agent.init()
    logger.info(
        "Services | gemini=%s | sarvam=%s | search=%s",
        bool(settings.gemini_api_key),
        bool(settings.sarvam_api_key),
        bool(settings.tavily_api_key),
    )
    yield
    logger.info("Shutting down VoiceOps AI Assistant")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VoiceOps AI Assistant",
        description="AI voice assistant with Gemini, web search, STT, and TTS.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    static_dir = ROOT_DIR / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
