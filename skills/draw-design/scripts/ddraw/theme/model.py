"""Theme model: semantic tokens for a light and a dark skin, bound to draw.io colours."""

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
    adaptive: bool = True
    primary: str = "light"

    @property
    def name(self) -> str:
        return str(self.raw.get("name", "custom"))

    @property
    def slug(self) -> str:
        return str(self.raw.get("slug", "custom"))

    def token(self, skin: str, role: str) -> str:
        return str(self.raw[skin][role])

    def solid(self, skin: str, role: str, alpha: float | None = None, over: str = "paper") -> str:
        """A token as opaque hex for one skin, composited over the `over` token."""
        bg = self.raw[skin][over]
        if color.parse(bg)[1] < 1.0:
            bg = color.composite(bg, self.raw[skin]["paper"])
        return color.composite(self.raw[skin][role], bg, alpha)

    def c(self, role: str, alpha: float | None = None, over: str = "paper") -> str:
        """A draw.io colour: `light-dark(light,dark)` when adaptive, else the primary skin's plain hex."""
        light = self.solid("light", role, alpha, over)
        dark = self.solid("dark", role, alpha, over)
        if not self.adaptive:
            return dark if self.primary == "dark" else light
        return light if light == dark else f"light-dark({light},{dark})"

    def series(self, index: int) -> str:
        light = str(self.raw["light"]["series"][index % len(self.raw["light"]["series"])])
        dark = str(self.raw["dark"]["series"][index % len(self.raw["dark"]["series"])])
        if not self.adaptive:
            return dark if self.primary == "dark" else light
        return f"light-dark({light},{dark})"

    def font(self, role: str) -> str:
        return str(self.raw["fonts"][role]["stack"])

    def font_family(self, role: str) -> str:
        return str(self.raw["fonts"][role]["family"])

    def palette(self) -> set[str]:
        """Every opaque colour a compiled diagram may legitimately use (for lint)."""
        out: set[str] = set()
        for skin in ("light", "dark"):
            for role in ROLES:
                for over in ("paper", "paper2"):
                    for a in (
                        None,
                        0.02,
                        0.03,
                        0.04,
                        0.05,
                        0.08,
                        0.10,
                        0.12,
                        0.20,
                        0.30,
                        0.40,
                        0.50,
                        0.80,
                        0.85,
                    ):
                        out.add(self.solid(skin, role, a, over).lower())
            for s in self.raw[skin].get("series", []):
                out.add(color.composite(s, self.solid(skin, "paper")).lower())
        out.update({"#ffffff", "none"})
        return out


def load_theme(path: Path | None = None, *, adaptive: bool = True, primary: str = "light") -> Theme:
    p = path or (THEMES_DIR / "default.json")
    raw = json.loads(p.read_text(encoding="utf-8"))
    missing = [r for r in ROLES if r not in raw.get("light", {}) or r not in raw.get("dark", {})]
    if missing:
        default = json.loads((THEMES_DIR / "default.json").read_text(encoding="utf-8"))
        for skin in ("light", "dark"):
            for r in missing:
                raw.setdefault(skin, {}).setdefault(r, default[skin][r])
        raw["_backfilled"] = missing
    return Theme(raw=raw, adaptive=adaptive, primary=primary)
