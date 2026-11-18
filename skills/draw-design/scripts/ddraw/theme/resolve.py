"""Theme resolution before every build (PRD §15.2): project marker → profile → installed theme → default."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ddraw.paths import THEMES_DIR, profiles_dir

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MARKER = re.compile(r"^profile:[ \t]*([^\s]+)[ \t]*\n?$")
MARKER_FILE = ".draw-design"


@dataclass
class Resolution:
    status: str  # profile | custom-unsaved | default-gate | marker-missing-profile | marker-invalid | default
    slug: str = ""
    path: Path | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "slug": self.slug,
            "path": str(self.path) if self.path else None,
            "notes": self.notes,
        }


def profile_path(slug: str) -> Path | None:
    if not SLUG.match(slug):
        return None
    return profiles_dir() / f"{slug}.json"


def find_project_root(start: Path) -> Path:
    cur = start.resolve()
    for p in (cur, *cur.parents):
        if (p / MARKER_FILE).is_file() or (p / ".git").exists():
            return p
    return cur


def read_marker(root: Path) -> tuple[str, str]:
    """Return (slug, error). Marker content is untrusted: accept only the one-line grammar."""
    f = root / MARKER_FILE
    if not f.is_file():
        return "", ""
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "", "marker is unreadable"
    if len(text) > 200:
        return "", "marker is too long"
    m = MARKER.match(text)
    if not m:
        return "", "marker must contain exactly one line: profile: <slug>"
    slug = m.group(1)
    if not SLUG.match(slug):
        return "", f"invalid profile slug {slug!r}"
    return slug, ""


def _is_default(path: Path) -> bool:
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        default = json.loads((THEMES_DIR / "default.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    keys = ("light", "dark", "fonts")
    return all(cur.get(k) == default.get(k) for k in keys)


def resolve(project: Path) -> Resolution:
    root = find_project_root(project)
    slug, err = read_marker(root)
    notes = []
    if err:
        notes.append(f"ignored {root / MARKER_FILE}: {err}")
    elif slug:
        if slug == "default":
            return Resolution("profile", "default", THEMES_DIR / "default.json", notes)
        p = profile_path(slug)
        if p is not None and p.is_file():
            return Resolution("profile", slug, p, notes)
        return Resolution("marker-missing-profile", slug, p, notes)
    active = THEMES_DIR / "active.json"
    if active.is_file():
        try:
            raw = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            notes.append("themes/active.json is not valid JSON; ignored")
        else:
            prof = raw.get("profile", {})
            if isinstance(prof, dict) and prof.get("slug"):
                return Resolution("profile", str(prof["slug"]), active, notes)
            if not _is_default(active):
                return Resolution("custom-unsaved", "", active, notes)
    status = "marker-invalid" if err else "default-gate"
    return Resolution(status, "default", THEMES_DIR / "default.json", notes)
