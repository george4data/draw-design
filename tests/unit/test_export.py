from __future__ import annotations

from pathlib import Path

import pytest

from ddraw.export import drawio_cli
from ddraw.pipeline import build
from helpers import example

CLI = drawio_cli.find()
needs_drawio = pytest.mark.skipif(CLI is None, reason="draw.io Desktop not installed")


def test_scale_bounds(tmp_path: Path) -> None:
    from ddraw.errors import DDError

    src = tmp_path / "a.drawio"
    src.write_text(build(example("architecture")).xml)
    with pytest.raises(DDError) as exc:
        drawio_cli.export(src, "png", scale=0.5, cli=drawio_cli.Cli(Path("/bin/false"), "0", []))
    assert exc.value.findings[0].code == "EXPORT-003"


def test_free_path(tmp_path: Path) -> None:
    p = tmp_path / "a.drawio.png"
    assert drawio_cli.free_path(p) == p
    p.write_text("x")
    assert drawio_cli.free_path(p).name == "a-1.drawio.png"


@needs_drawio
@pytest.mark.parametrize("fmt", ["png", "svg", "pdf", "drawio.svg"])
def test_export_formats(tmp_path: Path, fmt: str) -> None:
    src = tmp_path / "arch.drawio"
    src.write_text(build(example("architecture")).xml)
    out = drawio_cli.export(src, fmt, cli=CLI)
    assert out.exists() and out.stat().st_size > 1000
    if fmt.endswith("svg"):
        text = out.read_text()
        assert 'role="img"' in text and "<title id=" in text and "Checkout platform" in text
    if fmt == "png":
        with out.open("rb") as fh:
            head = fh.read(24)
        width = int.from_bytes(head[16:20], "big")
        assert abs(width - 960 * 2) <= 4
