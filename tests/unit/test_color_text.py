from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddraw.paths import THEMES_DIR
from ddraw.text.measure import ceil4, width
from ddraw.theme import color
from ddraw.theme.contrast import check
from ddraw.theme.model import load_theme


@pytest.mark.parametrize(
    ("role", "expected"),
    [("accent", 4.71), ("soft", 5.34), ("link", 6.13), ("muted", 6.11)],
)
def test_default_contrast_matches_reference(role: str, expected: float) -> None:
    theme = load_theme()
    ratio = color.contrast(theme.solid(role), theme.solid("paper"))
    assert ratio == pytest.approx(expected, abs=0.01)


def test_default_theme_passes_contract() -> None:
    assert [f for f in check(load_theme()) if f.severity == "error"] == []


def test_composite_rgba_over_paper() -> None:
    assert color.composite("rgba(45,49,66,0.12)", "#f5f5f5") == "#dddde0"
    assert color.composite("#bf4520", "#f5f5f5", 0.08) == "#f1e7e4"


def test_colours_are_plain_hex() -> None:
    theme = load_theme()
    assert theme.c("ink") == "#2d3142"
    assert theme.c("rule") == "#dddde0"  # rgba composited over paper


def test_legacy_two_skin_theme_keeps_light(tmp_path: Path) -> None:
    raw = json.loads((THEMES_DIR / "default.json").read_text())
    legacy = {k: v for k, v in raw.items() if k != "colors"}
    legacy["light"] = {**raw["colors"], "accent": "#005f73"}
    legacy["dark"] = {"paper": "#000000"}
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps(legacy))
    theme = load_theme(p)
    assert theme.c("accent") == "#005f73" and "dark" not in theme.raw and "light" not in theme.raw


def test_width_budget_counts_every_character() -> None:
    # 주문 v2.1: two wide syllables (1em each) + five narrow characters (0.6em each), at 12px
    assert width("주문 v2.1", 12, "sans") == pytest.approx((2 * 1.0 + 5 * 0.6) * 12)
    assert width("Шкаф ODF-2", 12, "sans") == pytest.approx(10 * 0.6 * 12)
    assert width("é", 10, "mono") == pytest.approx(6.2)
    assert width("é", 10, "mono") == pytest.approx(6.2)  # combining mark is free


def test_ceil4() -> None:
    assert [ceil4(v) for v in (0, 1, 4, 4.1, 7.9)] == [0, 4, 4, 8, 8]
