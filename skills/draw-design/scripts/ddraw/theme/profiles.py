"""Client profiles (PRD §15.3): named themes in ~/.draw-design/profiles/<slug>.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ddraw.errors import DDError, Finding
from ddraw.paths import THEMES_DIR, profiles_dir
from ddraw.theme.contrast import check
from ddraw.theme.model import ROLES, load_theme
from ddraw.theme.resolve import MARKER_FILE, SLUG, find_project_root

ACTIVE = THEMES_DIR / "active.json"


def _validate_slug(slug: str) -> None:
    if not SLUG.match(slug):
        raise DDError(
            [
                Finding(
                    "PROFILE-001",
                    f"invalid profile slug {slug!r}",
                    fix="lowercase letters, digits and hyphens, starting with a letter or digit",
                )
            ]
        )


def path_for(slug: str) -> Path:
    _validate_slug(slug)
    return profiles_dir() / f"{slug}.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DDError([Finding("PROFILE-002", f"cannot read {path}: {exc}")]) from exc
    if not isinstance(data, dict):
        raise DDError([Finding("PROFILE-002", f"{path} is not a JSON object")])
    return data


def _check_structure(data: dict[str, Any], where: str) -> list[Finding]:
    out = []
    for skin in ("light", "dark"):
        if not isinstance(data.get(skin), dict):
            out.append(Finding("PROFILE-003", f"{where}: missing {skin!r} token table"))
            continue
        missing = [r for r in ROLES if r not in data[skin]]
        if missing:
            out.append(
                Finding(
                    "PROFILE-003",
                    f"{where}: {skin} is missing roles {', '.join(missing)}",
                    severity="warn",
                    fix="missing roles are backfilled from the default theme",
                )
            )
    return out


def create(
    slug: str,
    name: str,
    *,
    source: Path | None = None,
    source_url: str = "",
    notes: str = "",
    force: bool = False,
) -> tuple[Path, list[Finding]]:
    """Create a profile from a theme file (default: the shipped default theme)."""
    if slug == "default":
        raise DDError([Finding("PROFILE-004", "the default profile is reserved")])
    target = path_for(slug)
    if target.exists() and not force:
        raise DDError(
            [
                Finding(
                    "PROFILE-005",
                    f"profile {slug!r} already exists at {target}",
                    fix="ask the user, then pass --force to overwrite (or use another slug)",
                )
            ]
        )
    data = _read(source or THEMES_DIR / "default.json")
    data.pop("_backfilled", None)
    findings = _check_structure(data, str(source or "default theme"))
    today = date.today().isoformat()
    created = _read(target).get("profile", {}).get("created", today) if target.exists() else today
    data["name"], data["slug"] = name, slug
    data["profile"] = {
        "name": name,
        "slug": slug,
        "sourceUrl": source_url or "none",
        "created": created,
        "updated": today,
        "notes": notes or "none",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    findings += check(load_theme(target))
    return target, findings


def list_profiles() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    d = profiles_dir()
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        entry = {"slug": p.stem, "path": str(p)}
        if not SLUG.match(p.stem):
            entry["status"] = "invalid file name"
        else:
            try:
                meta = _read(p).get("profile", {})
                entry.update(
                    {
                        "name": str(meta.get("name", p.stem)),
                        "updated": str(meta.get("updated", "")),
                        "sourceUrl": str(meta.get("sourceUrl", "none")),
                        "status": "ok" if meta.get("slug") == p.stem else "slug mismatch",
                    }
                )
            except DDError:
                entry["status"] = "unreadable"
        out.append(entry)
    return out


def show(slug: str) -> dict[str, Any]:
    p = path_for(slug)
    if not p.is_file():
        raise DDError([Finding("PROFILE-006", f"profile {slug!r} not found", fix="run: ddraw profile list")])
    data = _read(p)
    theme = load_theme(p)
    return {
        "profile": data.get("profile", {}),
        "path": str(p),
        "light": {r: theme.raw["light"][r] for r in ("paper", "ink", "muted", "accent", "link")},
        "dark": {r: theme.raw["dark"][r] for r in ("paper", "ink", "muted", "accent", "link")},
        "fonts": {k: v.get("family") for k, v in theme.raw["fonts"].items()},
        "contrast": [f.to_dict() for f in check(theme)],
    }


def use(slug: str, project: Path) -> Path:
    """Select a profile for one project by writing its marker file."""
    if slug != "default" and not path_for(slug).is_file():
        raise DDError([Finding("PROFILE-006", f"profile {slug!r} not found", fix="run: ddraw profile list")])
    _validate_slug(slug)
    root = find_project_root(project)
    marker = root / MARKER_FILE
    marker.write_text(f"profile: {slug}\n", encoding="utf-8")
    return marker


def load(slug: str) -> Path:
    """Make a profile the installed default for projects without a marker."""
    if slug == "default":
        return reset()
    src = path_for(slug)
    if not src.is_file():
        raise DDError([Finding("PROFILE-006", f"profile {slug!r} not found", fix="run: ddraw profile list")])
    ACTIVE.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return ACTIVE


def reset() -> Path:
    if ACTIVE.exists():
        ACTIVE.unlink()
    return THEMES_DIR / "default.json"


def delete(slug: str) -> Path:
    if slug == "default":
        raise DDError([Finding("PROFILE-004", "the default profile is reserved")])
    p = path_for(slug)
    if not p.is_file():
        raise DDError([Finding("PROFILE-006", f"profile {slug!r} not found")])
    p.unlink()
    return p
