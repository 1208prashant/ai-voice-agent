#!/usr/bin/env python3
"""Interactive CLI client for VoiceOps AI Assistant."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def text_mode(base_url: str, session_id: str | None) -> str | None:
    print("\nVoiceOps Text Mode")
    print("Commands: /quit, /reset, /history")
    print("-" * 40)

    async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            if not user_input:
                continue
            if user_input.lower() in {"/quit", "quit", "exit"}:
                break
            if user_input.lower() == "/reset":
                if session_id:
                    await client.delete(f"/api/sessions/{session_id}")
                    print("Session cleared.")
                    session_id = None
                continue
            if user_input.lower() == "/history" and session_id:
                resp = await client.get(f"/api/sessions/{session_id}/history")
                resp.raise_for_status()
                for msg in resp.json()["messages"]:
                    print(f"  [{msg['role']}] {msg['content'][:200]}")
                continue

            resp = await client.post(
                "/api/chat/text",
                json={"message": user_input, "session_id": session_id},
            )
            resp.raise_for_status()
            data = resp.json()
            session_id = data["session_id"]

            prefix = "[web search] " if data["used_web_search"] else ""
            print(f"\nAssistant: {prefix}{data['response_text']}")

    return session_id


async def voice_mode(base_url: str, session_id: str | None, duration: float) -> str | None:
    from src.services.voice_service import play_audio, record_audio

    print("\nVoiceOps Voice Mode")
    print("Press Enter to speak (or type text). Commands: /quit, /reset")
    print("-" * 40)

    async with httpx.AsyncClient(base_url=base_url, timeout=180.0) as client:
        while True:
            try:
                user_input = input("\n[Enter=voice, or type message]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            if user_input.lower() in {"/quit", "quit", "exit"}:
                break
            if user_input.lower() == "/reset":
                if session_id:
                    await client.delete(f"/api/sessions/{session_id}")
                    print("Session cleared.")
                    session_id = None
                continue

            if user_input:
                resp = await client.post(
                    "/api/chat/text",
                    json={"message": user_input, "session_id": session_id},
                )
            else:
                print(f"Listening for {duration:.0f}s...")
                wav_bytes = record_audio(duration_seconds=duration)
                resp = await client.post(
                    "/api/chat/voice",
                    files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
                    params={"session_id": session_id} if session_id else None,
                )

            resp.raise_for_status()
            data = resp.json()
            session_id = data["session_id"]
            transcript = data.get("transcript") or data.get("user_text", user_input)
            response_text = data["response_text"]
            used_search = data["used_web_search"]

            tts_payload = {"text": response_text}
            if data.get("response_language"):
                tts_payload["language_code"] = data["response_language"]
            tts_resp = await client.post("/api/tts", json=tts_payload)
            tts_resp.raise_for_status()
            audio_bytes = tts_resp.content

            prefix = "[web search] " if used_search else ""
            print(f"\nYou said: {transcript}")
            print(f"Assistant: {prefix}{response_text}")
            print("Speaking...")
            play_audio(audio_bytes, suffix=".wav")

    return session_id


async def check_health(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get("/api/health")
        resp.raise_for_status()
        data = resp.json()
        print(f"Status: {data['status']} (v{data['version']})")
        for name, ok in data["services"].items():
            mark = "OK" if ok else "NOT CONFIGURED"
            print(f"  {name}: {mark}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VoiceOps AI Assistant CLI")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="API base URL")
    parser.add_argument(
        "--mode",
        choices=["text", "voice"],
        default="text",
        help="Interaction mode (default: text)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Voice recording duration in seconds (voice mode)",
    )
    parser.add_argument("--health", action="store_true", help="Check API health and exit")
    args = parser.parse_args()

    if args.health:
        asyncio.run(check_health(args.url))
        return

    if args.mode == "voice":
        asyncio.run(voice_mode(args.url, None, args.duration))
    else:
        asyncio.run(text_mode(args.url, None))


if __name__ == "__main__":
    main()
