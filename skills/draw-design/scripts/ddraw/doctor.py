"""Environment diagnostics (PRD §17.3). Read-only."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddraw import __version__, registry
from ddraw.export import drawio_cli
from ddraw.paths import DATA_DIR, PACKAGE_DIR, SCHEMAS_DIR, SKILL_ROOT, THEMES_DIR, profiles_dir
from ddraw.theme.contrast import check as contrast_check
from ddraw.theme.model import load_theme
from ddraw.theme.resolve import find_project_root, read_marker


@dataclass
class Check:
    name: str
    status: str
    message: str
    fix: str = ""


def _fonts_installed(families: list[str]) -> dict[str, bool]:
    names = {f: False for f in families}
    listing = ""
    if shutil.which("fc-list"):
        try:
            listing = subprocess.run(
                ["fc-list", ":", "family"], capture_output=True, text=True, timeout=20
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            listing = ""
    dirs = [
        Path.home() / "Library/Fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path.home() / ".local/share/fonts",
        Path("/usr/share/fonts"),
    ]
    files = []
    for d in dirs:
        if d.is_dir():
            try:
                files += [
                    p.name.lower() for p in d.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc")
                ]
            except OSError:
                continue
    for fam in families:
        key = fam.lower().replace(" ", "")
        names[fam] = fam.lower() in listing.lower() or any(
            key in f.replace(" ", "").replace("-", "") for f in files
        )
    return names


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3])


def _icons_check(installed: str) -> Check:
    from ddraw.icons import catalog

    fams = catalog.families()
    if not fams:
        return Check(
            "icons", "fail", "shape catalog missing (data/shapes/families.json)", "reinstall the plugin"
        )
    total = sum(f.count for f in fams.values())
    verified = catalog.verified_with()
    msg = f"{total} vendor icons in {len(fams)} families, verified with draw.io {verified or 'unknown'}"
    if installed and verified and _version_tuple(installed) < _version_tuple(verified):
        return Check(
            "icons",
            "warn",
            f"{msg}; installed draw.io {installed} is older, so some icons may draw as empty boxes",
            "update draw.io Desktop",
        )
    return Check("icons", "pass", msg)


def run(project: Path) -> list[Check]:
    checks: list[Check] = []
    v = sys.version_info
    checks.append(
        Check(
            "python",
            "pass" if v >= (3, 10) else "fail",
            f"Python {v.major}.{v.minor}.{v.micro} at {sys.executable}",
            "" if v >= (3, 10) else "install Python 3.10 or newer",
        )
    )
    required = [
        SKILL_ROOT / "SKILL.md",
        PACKAGE_DIR / "cli.py",
        SCHEMAS_DIR / "spec.schema.json",
        THEMES_DIR / "default.json",
        DATA_DIR / "presets.json",
        DATA_DIR / "budgets.json",
    ]
    missing = [str(p.relative_to(SKILL_ROOT)) for p in required if not p.exists()]
    checks.append(
        Check(
            "skill-integrity",
            "fail" if missing else "pass",
            f"missing: {', '.join(missing)}" if missing else f"skill files present at {SKILL_ROOT}",
            "reinstall the plugin" if missing else "",
        )
    )
    try:
        n = len(registry.shipped())
        checks.append(Check("registry", "pass", f"ddraw {__version__}; {n} shipped diagram types"))
    except Exception as exc:
        checks.append(Check("registry", "fail", f"type registry failed to load: {exc}"))
    cli = drawio_cli.find()
    if cli:
        checks.append(Check("drawio-cli", "pass", f"draw.io {cli.version} at {cli.path}"))
    else:
        checks.append(
            Check(
                "drawio-cli",
                "warn",
                "draw.io Desktop not found: export and preview unavailable",
                "install draw.io Desktop or set DRAWIO_CLI",
            )
        )
    checks.append(_icons_check(cli.version if cli else ""))
    if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
        ok = bool(shutil.which("xvfb-run"))
        checks.append(
            Check(
                "display",
                "pass" if ok else "warn",
                "headless: xvfb-run available" if ok else "no DISPLAY and no xvfb-run",
                "" if ok else "install xvfb (apt install xvfb)",
            )
        )
    theme = load_theme()
    fams = sorted({theme.font_family(r) for r in ("title", "sans", "mono")})
    found = _fonts_installed(fams)
    absent = [f for f, ok in found.items() if not ok]
    checks.append(
        Check(
            "fonts",
            "warn" if absent else "pass",
            f"not installed locally: {', '.join(absent)} (exports substitute fallbacks)"
            if absent
            else "theme fonts installed",
            "install the fonts (all SIL OFL) for faithful exports" if absent else "",
        )
    )
    pdir = profiles_dir()
    if pdir.exists():
        writable = os.access(pdir, os.W_OK)
        checks.append(
            Check(
                "profiles",
                "pass" if writable else "warn",
                f"profile library {pdir}",
                "" if writable else f"make {pdir} writable",
            )
        )
    else:
        checks.append(Check("profiles", "pass", f"no profile library yet ({pdir} is created on first save)"))
    root = find_project_root(project)
    slug, err = read_marker(root)
    if err:
        checks.append(Check("marker", "warn", f"{root / '.draw-design'}: {err}", "fix or remove the marker"))
    elif slug:
        checks.append(Check("marker", "pass", f"project marker selects profile {slug!r}"))
    bad = contrast_check(theme)
    checks.append(
        Check(
            "contrast",
            "warn" if bad else "pass",
            f"{len(bad)} contrast issue(s) in the default theme" if bad else "default theme passes contrast",
        )
    )
    return checks


def render(checks: list[Check], as_json: bool, strict: bool) -> tuple[str, int]:
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("pass", "warn", "fail")}
    status = (
        "FAIL" if counts["fail"] or (strict and counts["warn"]) else ("WARN" if counts["warn"] else "PASS")
    )
    lines = [
        f"Doctor summary: {status} ({counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail)"
    ]
    lines += [f"[{c.status.upper()}] {c.message}" for c in checks]
    actions = [c for c in checks if c.status != "pass" and c.fix]
    if actions:
        lines.append("Next actions:")
        lines += [f"- {c.name}: {c.fix}" for c in actions]
    if as_json:
        payload: dict[str, Any] = {
            "status": status.lower(),
            "counts": counts,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    **({"fix": c.fix} if c.fix else {}),
                }
                for c in checks
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        lines.append(json.dumps(payload, indent=2))
    return "\n".join(lines), 1 if status == "FAIL" else 0
