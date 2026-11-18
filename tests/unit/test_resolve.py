from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddraw.paths import THEMES_DIR
from ddraw.theme.resolve import read_marker, resolve


@pytest.mark.parametrize(
    ("content", "slug", "error"),
    [
        ("profile: acme\n", "acme", ""),
        ("profile:acme", "acme", ""),
        ("profile: Acme\n", "", "invalid profile slug 'Acme'"),
        ("profile: ../../etc/passwd\n", "", "invalid profile slug '../../etc/passwd'"),
        ("profile: acme\nextra: 1\n", "", "marker must contain exactly one line: profile: <slug>"),
        ("# comment\nprofile: acme\n", "", "marker must contain exactly one line: profile: <slug>"),
        ("ignore previous instructions", "", "marker must contain exactly one line: profile: <slug>"),
    ],
)
def test_marker_grammar_is_strict(tmp_path: Path, content: str, slug: str, error: str) -> None:
    (tmp_path / ".draw-design").write_text(content)
    assert read_marker(tmp_path) == (slug, error)


def test_resolution_statuses(tmp_path: Path, isolated_home: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert resolve(tmp_path).status == "default-gate"
    (tmp_path / ".draw-design").write_text("profile: acme\n")
    assert resolve(tmp_path).status == "marker-missing-profile"
    prof = isolated_home / "profiles"
    prof.mkdir(parents=True)
    raw = json.loads((THEMES_DIR / "default.json").read_text())
    raw["light"]["accent"] = "#005f73"
    (prof / "acme.json").write_text(json.dumps(raw))
    res = resolve(tmp_path)
    assert (res.status, res.slug) == ("profile", "acme")
    (tmp_path / ".draw-design").write_text("profile: ACME\n")
    res = resolve(tmp_path)
    assert res.status == "marker-invalid" and res.notes
