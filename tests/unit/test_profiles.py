from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddraw.cli import main
from ddraw.errors import DDError
from ddraw.lint.runner import lint_text
from ddraw.paths import THEMES_DIR
from ddraw.pipeline import build
from ddraw.theme import profiles
from helpers import EXAMPLES, example


def brand_theme(tmp_path: Path) -> Path:
    raw = json.loads((THEMES_DIR / "default.json").read_text())
    raw["colors"]["accent"] = "#005f73"
    p = tmp_path / "acme-theme.json"
    p.write_text(json.dumps(raw))
    return p


def test_profile_lifecycle(tmp_path: Path, isolated_home: Path) -> None:
    path, findings = profiles.create(
        "acme", "Acme Corp", source=brand_theme(tmp_path), source_url="https://acme.test"
    )
    assert path == isolated_home / "profiles" / "acme.json"
    assert not [f for f in findings if f.severity == "error"]
    assert [p["slug"] for p in profiles.list_profiles()] == ["acme"]
    info = profiles.show("acme")
    assert info["colors"]["accent"] == "#005f73" and info["profile"]["sourceUrl"] == "https://acme.test"
    with pytest.raises(DDError):
        profiles.create("acme", "Again")
    with pytest.raises(DDError):
        profiles.create("default", "Nope")
    with pytest.raises(DDError):
        profiles.create("../evil", "Nope")
    profiles.delete("acme")
    assert profiles.list_profiles() == []


def test_project_marker_selects_profile_for_builds(tmp_path: Path) -> None:
    profiles.create("acme", "Acme", source=brand_theme(tmp_path))
    project = tmp_path / "repo"
    (project / ".git").mkdir(parents=True)
    profiles.use("acme", project)
    assert (project / ".draw-design").read_text() == "profile: acme\n"
    result = build(example("architecture"), project=project)
    assert result.theme.slug == "acme"
    assert "#005f73" in result.xml and "#bf4520" not in result.xml
    assert [f for f in lint_text(result.xml) if f.severity == "error"] == []


def test_cli_profile_verbs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profile", "new", "beta", "--name", "Beta", "--source", str(brand_theme(tmp_path))]) == 0
    assert main(["profile", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["slug"] == "beta"
    assert main(["profile", "delete", "beta"]) == 2  # needs --yes
    assert main(["profile", "delete", "beta", "--yes"]) == 0
    assert main(["profile", "show", "beta"]) == 2


def test_build_with_explicit_profile(tmp_path: Path) -> None:
    profiles.create("gamma", "Gamma", source=brand_theme(tmp_path))
    out = tmp_path / "a.drawio"
    assert main(["build", str(EXAMPLES / "architecture.dd.json"), "-o", str(out), "--profile", "gamma"]) == 0
    assert "#005f73" in out.read_text()
