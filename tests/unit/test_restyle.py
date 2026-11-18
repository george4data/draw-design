from __future__ import annotations

import base64
import re
import urllib.parse
import zlib
from pathlib import Path

import pytest

from ddraw.cli import main
from ddraw.errors import DDError
from ddraw.importers.restyle import restyle_text, treatment_for
from ddraw.lint.runner import lint_text
from ddraw.theme.model import load_theme
from helpers import ROOT

FIXTURE = ROOT / "tests" / "import_fixtures" / "sample-architecture.drawio"


@pytest.mark.parametrize(
    ("fill", "expected"),
    [
        ("#dae8fc", "backend"),
        ("#d5e8d4", "backend"),
        ("#f8cecc", "optional"),
        ("#e1d5e7", "external"),
        ("#f5f5f5", "store"),
        ("none", "backend"),
        ("#ffffff", "backend"),
        ("bogus", "backend"),
    ],
)
def test_colour_to_treatment(fill: str, expected: str) -> None:
    assert treatment_for(fill) == expected


def test_restyle_fixture_keeps_geometry_and_applies_theme() -> None:
    src = FIXTURE.read_text()
    xml, report = restyle_text(src, load_theme(), focal={"gw"})
    assert report.vertices >= 8 and report.edges >= 6 and report.focal == ["gw"]
    assert "mxgraph.aws4.bucket" in report.kept
    geo = re.compile(r'<mxGeometry x="([\d.]+)" y="([\d.]+)"')
    assert geo.findall(src)[:5] == geo.findall(xml)[:5]
    assert "shadow=1" not in xml and "#dae8fc" not in xml and "light-dark(" not in xml
    assert not [f for f in lint_text(xml) if f.code.startswith("LR-S") and f.severity == "error"]


def test_restyle_snaps_to_grid() -> None:
    xml, report = restyle_text(FIXTURE.read_text(), load_theme(), snap=True)
    assert report.snapped
    for x, y in re.findall(r'<mxGeometry x="(-?\d+)" y="(-?\d+)" width', xml):
        assert int(x) % 4 == 0 and int(y) % 4 == 0


def test_restyle_compressed_input() -> None:
    inner = FIXTURE.read_text().split("<diagram", 1)[1].split(">", 1)[1].rsplit("</diagram>", 1)[0]
    enc = urllib.parse.quote(inner.strip(), safe="-_.!~*'()")
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    payload = base64.b64encode(co.compress(enc.encode()) + co.flush()).decode()
    xml, report = restyle_text(f'<mxfile><diagram id="p" name="P">{payload}</diagram></mxfile>', load_theme())
    assert report.vertices > 0 and "<mxGraphModel" in xml


def test_restyle_rejects_unsafe_and_foreign() -> None:
    with pytest.raises(DDError):
        restyle_text('<!DOCTYPE x [<!ENTITY a "b">]><mxfile/>', load_theme())
    with pytest.raises(DDError):
        restyle_text("<svg/>", load_theme())


def test_cli_import(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "legacy.drawio"
    src.write_text(FIXTURE.read_text())
    assert main(["import", str(src), "--snap", "--focal", "gw"]) == 0
    assert (tmp_path / "legacy.restyled.drawio").is_file()
    assert "Restyle report" in capsys.readouterr().out
    assert main(["import", str(src), "--mode", "redraw"]) == 2
