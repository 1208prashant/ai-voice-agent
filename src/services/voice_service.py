"""Microphone capture and audio utilities."""

from __future__ import annotations

import io
import logging
import wave

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1


def record_audio(duration_seconds: float = 5.0, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Record from the default microphone and return WAV bytes."""
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "sounddevice and numpy are required for microphone capture. "
            "Install with: pip install sounddevice numpy"
        ) from exc

    logger.info("Recording %.1fs of audio...", duration_seconds)
    frames = int(duration_seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=DEFAULT_CHANNELS, dtype="int16")
    sd.wait()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(DEFAULT_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())

    return buffer.getvalue()


def save_wav(audio_bytes: bytes, path: str) -> None:
    with open(path, "wb") as handle:
        handle.write(audio_bytes)


def play_audio(audio_bytes: bytes, suffix: str = ".wav") -> None:
    """Play audio using the system player when available."""
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        if Path("/usr/bin/afplay").exists():
            subprocess.run(["afplay", tmp_path], check=False)
        else:
            logger.warning("No audio player found; saved response to %s", tmp_path)
            return
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def play_mp3(audio_bytes: bytes) -> None:
    """Backward-compatible alias for play_audio."""
    play_audio(audio_bytes, suffix=".mp3")
