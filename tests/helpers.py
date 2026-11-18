from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "draw-design"
EXAMPLES = SKILL / "examples"
GOLDEN = ROOT / "tests" / "golden"
FIXTURES = ROOT / "tests" / "lint_fixtures"


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / f"{name}.dd.json").read_text(encoding="utf-8"))
    return data


def shipped_examples() -> list[str]:
    return sorted(p.name[: -len(".dd.json")] for p in EXAMPLES.glob("*.dd.json"))
