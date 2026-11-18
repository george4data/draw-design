"""Filesystem locations of the installed skill and of user state."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_ROOT = PACKAGE_DIR.parent.parent
DATA_DIR = SKILL_ROOT / "data"
THEMES_DIR = SKILL_ROOT / "themes"
SCHEMAS_DIR = SKILL_ROOT / "schemas"
EXAMPLES_DIR = SKILL_ROOT / "examples"
REFERENCES_DIR = SKILL_ROOT / "references"


def user_home() -> Path:
    """The draw-design user state directory (profiles, icon packs)."""
    override = os.environ.get("DRAW_DESIGN_HOME")
    if override:
        return Path(override)
    return Path.home() / ".draw-design"


def profiles_dir() -> Path:
    return user_home() / "profiles"
