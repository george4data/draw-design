"""Colour parsing, compositing and WCAG contrast."""

from __future__ import annotations

import re

RGB = tuple[float, float, float]

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGBA = re.compile(r"^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$")


def parse(value: str) -> tuple[RGB, float]:
    """Parse `#rgb`, `#rrggbb`, `rgb()` or `rgba()` into (rgb 0-255, alpha 0-1)."""
    v = value.strip()
    m = _HEX.match(v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (float(int(h[0:2], 16)), float(int(h[2:4], 16)), float(int(h[4:6], 16))), 1.0
    m = _RGBA.match(v)
    if m:
        r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return (r, g, b), a
    raise ValueError(f"unsupported colour {value!r}")


def to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def composite(fg: str, bg: str, alpha: float | None = None) -> str:
    """Blend `fg` (optionally at an extra `alpha`) over opaque `bg`; return opaque hex."""
    (fr, fg_, fb), fa = parse(fg)
    (br, bg_, bb), ba = parse(bg)
    if ba < 1.0:
        raise ValueError(f"background {bg!r} must be opaque")
    a = fa * (1.0 if alpha is None else alpha)
    return to_hex((fr * a + br * (1 - a), fg_ * a + bg_ * (1 - a), fb * a + bb * (1 - a)))


def _channel(c: float) -> float:
    s = c / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    (r, g, b), _ = parse(color)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
