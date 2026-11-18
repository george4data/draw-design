"""Conservative text width budget (PRD §11.6, FR-039e)."""

from __future__ import annotations

import math
import unicodedata

ADVANCE = {"sans": 0.60, "mono": 0.62, "serif": 0.50}


def char_advance(ch: str, kind: str) -> float:
    if unicodedata.category(ch) in ("Mn", "Me"):
        return 0.0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 1.0
    return ADVANCE[kind]


def width(text: str, size: float, kind: str = "sans", letter_spacing_em: float = 0.0) -> float:
    if not text:
        return 0.0
    em = sum(char_advance(ch, kind) for ch in text)
    return em * size + letter_spacing_em * size * max(0, len(text) - 1)


def has_wide(text: str) -> bool:
    return any(unicodedata.east_asian_width(ch) in ("W", "F") for ch in text)


def ceil4(v: float) -> int:
    return int(math.ceil(v / 4.0) * 4)


def floor4(v: float) -> int:
    return int(math.floor(v / 4.0) * 4)


def round4(v: float) -> int:
    return int(round(v / 4.0) * 4)
