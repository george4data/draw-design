from __future__ import annotations

import pytest

from ddraw.text.measure import ceil4, width
from ddraw.theme import color
from ddraw.theme.contrast import check
from ddraw.theme.model import load_theme


@pytest.mark.parametrize(
    ("skin", "role", "expected"),
    [
        ("light", "accent", 4.71),
        ("light", "soft", 5.34),
        ("light", "link", 6.13),
        ("light", "muted", 6.11),
        ("dark", "accent", 5.21),
        ("dark", "soft", 4.78),
        ("dark", "link", 4.76),
    ],
)
def test_default_contrast_matches_reference(skin: str, role: str, expected: float) -> None:
    theme = load_theme()
    ratio = color.contrast(theme.solid(skin, role), theme.solid(skin, "paper"))
    assert ratio == pytest.approx(expected, abs=0.01)


def test_default_theme_passes_contract() -> None:
    assert [f for f in check(load_theme()) if f.severity == "error"] == []


def test_composite_rgba_over_paper() -> None:
    assert color.composite("rgba(45,49,66,0.12)", "#f5f5f5") == "#dddde0"
    assert color.composite("#bf4520", "#f5f5f5", 0.08) == "#f1e7e4"


def test_light_dark_value() -> None:
    theme = load_theme()
    assert theme.c("ink") == "light-dark(#2d3142,#f5f5f5)"
    plain = load_theme(adaptive=False)
    assert plain.c("ink") == "#2d3142"


def test_width_budget_counts_every_character() -> None:
    # 주문 v2.1: two wide syllables (1em each) + five narrow characters (0.6em each), at 12px
    assert width("주문 v2.1", 12, "sans") == pytest.approx((2 * 1.0 + 5 * 0.6) * 12)
    assert width("Шкаф ODF-2", 12, "sans") == pytest.approx(10 * 0.6 * 12)
    assert width("é", 10, "mono") == pytest.approx(6.2)
    assert width("é", 10, "mono") == pytest.approx(6.2)  # combining mark is free


def test_ceil4() -> None:
    assert [ceil4(v) for v in (0, 1, 4, 4.1, 7.9)] == [0, 4, 4, 8, 8]
