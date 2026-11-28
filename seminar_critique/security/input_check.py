"""Reject seminar material that cannot be critiqued. Owner: Tin.

Careless-user scenario (AT1, D3): a student submits an empty file, pastes almost
nothing, or passes the raw bytes of a PDF/DOCX instead of its text. Before D3 the
pipeline still called the LLM and returned a fluent critique of nothing, which looks
like a success. `check_material` stops the run before any LLM call instead.

It is a usability guard, not an injection defence: it does not look for instructions
in the text (the <untrusted> wrapper and the system policy handle that).
"""
from __future__ import annotations

import unicodedata

MIN_WORDS = 15
MAX_BAD_CHAR_RATIO = 0.10
# Magic bytes of files that are not plain text, as they appear when read as text.
BINARY_PREFIXES = ("%PDF-", "PK\x03\x04", "\x89PNG", "\xd0\xcf\x11\xe0", "{\\rtf")


class InvalidMaterial(ValueError):
    """The seminar material is empty, too short or not text."""


def check_material(text: object) -> str:
    """Return `text` unchanged if it can be critiqued, else raise InvalidMaterial."""
    if not isinstance(text, str):
        raise InvalidMaterial(f"material must be text, got {type(text).__name__}")
    stripped = text.strip()
    if not stripped:
        raise InvalidMaterial("material is empty: paste the text of the paper or slides")
    if stripped.startswith(BINARY_PREFIXES):
        raise InvalidMaterial(
            "material looks like a binary file (PDF/DOCX/PNG/RTF), not its text: "
            "extract the text first"
        )
    sample = stripped[:5000]
    bad = sum(
        1 for ch in sample
        if ch == "�" or (unicodedata.category(ch) in {"Cc", "Cs"} and ch not in "\n\t\r")
    )
    if bad / len(sample) > MAX_BAD_CHAR_RATIO:
        raise InvalidMaterial("material is mostly control or undecodable characters, not text")
    words = len(stripped.split())
    if words < MIN_WORDS:
        raise InvalidMaterial(
            f"material has {words} words; at least {MIN_WORDS} are needed to critique a claim"
        )
    return text
