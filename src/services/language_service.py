"""Sarvam BCP-47 language codes and minimal script-based helpers for text chat."""

from __future__ import annotations

import re

SUPPORTED_TTS_LANGUAGES = {
    "en-IN",
    "hi-IN",
    "mr-IN",
    "gu-IN",
    "bn-IN",
    "ta-IN",
    "te-IN",
    "kn-IN",
    "ml-IN",
    "pa-IN",
    "od-IN",
}

LANGUAGE_LABELS = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
    "bn-IN": "Bengali",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

GUJARATI = re.compile(r"[\u0A80-\u0AFF]")
BENGALI = re.compile(r"[\u0980-\u09FF]")
TAMIL = re.compile(r"[\u0B80-\u0BFF]")
TELUGU = re.compile(r"[\u0C00-\u0C7F]")
KANNADA = re.compile(r"[\u0C80-\u0CFF]")
MALAYALAM = re.compile(r"[\u0D00-\u0D7F]")
GURMUKHI = re.compile(r"[\u0A00-\u0A7F]")
ODIA = re.compile(r"[\u0B00-\u0B7F]")
DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# Native-script phrases when the user explicitly asks to switch language (text chat only).
EXPLICIT_LANGUAGE_REQUESTS = {
    "हिंदी": "hi-IN",
    "मराठी": "mr-IN",
    "ગુજરાતી": "gu-IN",
}


def normalize_language_code(code: str | None) -> str | None:
    if not code:
        return None
    cleaned = code.strip()
    if cleaned.lower() in {"unknown", "auto", ""}:
        return None
    if cleaned in SUPPORTED_TTS_LANGUAGES:
        return cleaned
    aliases = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
        "gu": "gu-IN",
        "bn": "bn-IN",
        "ta": "ta-IN",
        "te": "te-IN",
        "kn": "kn-IN",
        "ml": "ml-IN",
        "pa": "pa-IN",
        "od": "od-IN",
    }
    return aliases.get(cleaned.lower(), cleaned if cleaned.endswith("-IN") else None)


def detect_script_language(text: str) -> str | None:
    """Detect language from Unicode script when unambiguous (text chat fallback only).

    Devanagari is shared by Hindi and Marathi — leave that to Sarvam STT auto-detect
    or session language instead of guessing from keywords.
    """
    if not text or not text.strip():
        return None
    if GUJARATI.search(text):
        return "gu-IN"
    if BENGALI.search(text):
        return "bn-IN"
    if TAMIL.search(text):
        return "ta-IN"
    if TELUGU.search(text):
        return "te-IN"
    if KANNADA.search(text):
        return "kn-IN"
    if MALAYALAM.search(text):
        return "ml-IN"
    if GURMUKHI.search(text):
        return "pa-IN"
    if ODIA.search(text):
        return "od-IN"
    return None


def detect_explicit_language_request(text: str) -> str | None:
    """Detect when the user explicitly names a language in native script."""
    for token, code in EXPLICIT_LANGUAGE_REQUESTS.items():
        if token in text:
            return code
    return None


def resolve_language(
    user_text: str = "",
    detected: str | None = None,
    session_language: str | None = None,
    fallback: str = "en-IN",
) -> str:
    """Pick reply/TTS language.

    Priority:
    1. Sarvam STT detected language (voice)
    2. Session language from prior turns
    3. Explicit native-script language request (text)
    4. Unambiguous script detection (text, e.g. Gujarati)
    5. Default fallback
    """
    for candidate in (detected, session_language):
        normalized = normalize_language_code(candidate)
        if normalized:
            return normalized

    explicit = detect_explicit_language_request(user_text)
    if explicit:
        return explicit

    script_lang = detect_script_language(user_text)
    if script_lang:
        return script_lang

    return fallback


def language_instruction(code: str) -> str:
    label = LANGUAGE_LABELS.get(code, code)
    if code == "en-IN":
        return (
            "Reply in natural English (Indian en-IN is fine). "
            "Match the user's language if they switch to Hindi, Marathi, Gujarati, or another supported language."
        )
    return (
        f"Reply entirely in {label} ({code}) using natural spoken phrasing. "
        "Do not switch to English unless the user does."
    )


def is_indic_text(text: str) -> bool:
    return bool(
        DEVANAGARI.search(text)
        or GUJARATI.search(text)
        or BENGALI.search(text)
        or TAMIL.search(text)
        or TELUGU.search(text)
        or KANNADA.search(text)
        or MALAYALAM.search(text)
        or GURMUKHI.search(text)
        or ODIA.search(text)
    )
