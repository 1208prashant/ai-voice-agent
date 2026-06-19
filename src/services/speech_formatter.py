"""Prepare assistant text for natural text-to-speech."""

from __future__ import annotations

import re

from src.services.language_service import is_indic_text


def prepare_for_speech(text: str) -> str:
    """Strip written-only formatting; preserve Indic scripts as-is."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    if is_indic_text(cleaned):
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    replacements = {
        "e.g.": "for example",
        "i.e.": "that is",
        "etc.": "and so on",
        "vs.": "versus",
        "API": "A P I",
        "URL": "U R L",
        "SSH": "S S H",
        "SSL": "S S L",
        "HTTP": "H T T P",
        "HTTPS": "H T T P S",
    }
    for src, dst in replacements.items():
        cleaned = re.sub(rf"\b{re.escape(src)}\b", dst, cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
