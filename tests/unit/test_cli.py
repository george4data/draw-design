from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddraw.cli import main
from helpers import EXAMPLES


def test_types_lists_shipped(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["types", "--json"]) == 0
    slugs = {t["slug"] for t in json.loads(capsys.readouterr().out)}
    assert {"architecture", "flowchart"} <= slugs
    assert main(["types", "--all", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 50


def test_build_and_lint_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "a.drawio"
    assert main(["build", str(EXAMPLES / "architecture.dd.json"), "-o", str(out), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["stats"]["nodes"] == 7
    assert main(["lint", str(out), "--json", "--strict"]) == 0


def test_validate_reports_json_pointer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = json.loads((EXAMPLES / "architecture.dd.json").read_text())
    spec["edges"][0]["to"] = "ghost"
    p = tmp_path / "bad.dd.json"
    p.write_text(json.dumps(spec))
    assert main(["validate", str(p), "--json"]) == 1
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert {"code": "SPEC-023", "pointer": "/edges/0/to"}.items() <= findings[0].items()


def test_new_scaffold(tmp_path: Path) -> None:
    out = tmp_path / "x.dd.json"
    assert main(["new", "flowchart", "-o", str(out)]) == 0
    assert json.loads(out.read_text())["type"] == "flowchart"
    assert main(["new", "sankey", "-o", str(tmp_path / "y.json")]) == 2


def test_unreadable_spec_is_usage_error(tmp_path: Path) -> None:
    p = tmp_path / "broken.dd.json"
    p.write_text("{ not json")
    assert main(["build", str(p)]) == 2


def test_theme_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["theme", "check"]) == 0
