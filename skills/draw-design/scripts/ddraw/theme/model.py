"""Theme model: semantic colour and font tokens, bound to draw.io colours."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ddraw.paths import THEMES_DIR
from ddraw.theme import color

ROLES = (
    "paper",
    "paper2",
    "ink",
    "inkStrong",
    "muted",
    "soft",
    "rule",
    "ruleSolid",
    "accent",
    "accentTint",
    "link",
    "nodeFill",
)
FONT_ROLES = ("title", "sans", "mono", "callout")


@dataclass
class Theme:
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("name", "custom"))

    @property
    def slug(self) -> str:
        return str(self.raw.get("slug", "custom"))

    @property
    def colors(self) -> dict[str, Any]:
        return dict(self.raw["colors"])

    def token(self, role: str) -> str:
        return str(self.raw["colors"][role])

    def solid(self, role: str, alpha: float | None = None, over: str = "paper") -> str:
        """A token as opaque hex, composited over the `over` token."""
        tokens = self.raw["colors"]
        bg = tokens[over]
        if color.parse(bg)[1] < 1.0:
            bg = color.composite(bg, tokens["paper"])
        return color.composite(tokens[role], bg, alpha)

    def c(self, role: str, alpha: float | None = None, over: str = "paper") -> str:
        """A draw.io colour: the token as plain opaque hex."""
        return self.solid(role, alpha, over)

    def series(self, index: int) -> str:
        series = self.raw["colors"]["series"]
        return str(series[index % len(series)])

    def font(self, role: str) -> str:
        return str(self.raw["fonts"][role]["stack"])

    def font_family(self, role: str) -> str:
        return str(self.raw["fonts"][role]["family"])

    def palette(self) -> set[str]:
        """Every opaque colour a compiled diagram may legitimately use (for lint)."""
        out: set[str] = set()
        alphas = (None, 0.02, 0.03, 0.04, 0.05, 0.08, 0.10, 0.12, 0.20, 0.30, 0.40, 0.50, 0.80, 0.85)
        for role in ROLES:
            for over in ("paper", "paper2"):
                for a in alphas:
                    out.add(self.solid(role, a, over).lower())
        for s in self.raw["colors"].get("series", []):
            out.add(color.composite(s, self.solid("paper")).lower())
        out.update({"#ffffff", "none"})
        return out


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept the pre-0.1 two-skin layout (`light` + `dark`): keep the light skin as `colors`."""
    if "colors" not in raw and isinstance(raw.get("light"), dict):
        raw["colors"] = raw["light"]
    raw.pop("light", None)
    raw.pop("dark", None)
    return raw


def load_theme(path: Path | None = None) -> Theme:
    p = path or (THEMES_DIR / "default.json")
    raw = normalize(json.loads(p.read_text(encoding="utf-8")))
    tokens = raw.setdefault("colors", {})
    missing = [r for r in ROLES if r not in tokens]
    if missing:
        default = json.loads((THEMES_DIR / "default.json").read_text(encoding="utf-8"))
        for r in missing:
            tokens[r] = default["colors"][r]
        raw["_backfilled"] = missing
    return Theme(raw=raw)
