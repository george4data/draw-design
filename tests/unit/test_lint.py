from __future__ import annotations

import base64
import re
import urllib.parse
import zlib

from ddraw.lint.runner import lint_text
from ddraw.pipeline import build
from helpers import example


def doc(cells: str, extra_model: str = "") -> str:
    return (
        '<mxfile><diagram id="p" name="P"><mxGraphModel pageWidth="400" pageHeight="300"'
        f"{extra_model}><root>"
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        f"{cells}</root></mxGraphModel></diagram></mxfile>"
    )


def v(cid: str, x: float, y: float, w: float = 80, h: float = 48, style: str = "rounded=1;") -> str:
    return (
        f'<mxCell id="{cid}" value="{cid}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def e(cid: str, s: str, t: str, style: str = "", points: str = "") -> str:
    arr = f'<Array as="points">{points}</Array>' if points else ""
    return (
        f'<mxCell id="{cid}" style="{style}" edge="1" parent="1" source="{s}" target="{t}">'
        f'<mxGeometry relative="1" as="geometry">{arr}</mxGeometry></mxCell>'
    )


def codes(text: str) -> set[str]:
    return {f.code for f in lint_text(text) if f.severity == "error"}


def test_clean_minimal_file() -> None:
    assert codes(doc(v("a", 40, 40) + v("b", 240, 40))) == set()


def test_structure_errors() -> None:
    assert "LR-S001" in codes("<html/>")
    assert "LR-S001" in codes("<mxfile><diagram")
    assert "LR-S001" in codes('<!DOCTYPE x [<!ENTITY a "b">]><mxfile/>')
    bad_parent = (
        '<mxCell id="x" style="" vertex="1" parent="nope">'
        '<mxGeometry width="4" height="4" as="geometry"/></mxCell>'
    )
    assert "LR-S002" in codes(doc(bad_parent))
    assert "LR-S002" in codes(doc(v("a", 0, 0) + v("a", 100, 0)))
    assert "LR-S003" in codes(doc(v("a", 0, 0) + e("e", "a", "ghost")))


def test_script_and_links_rejected() -> None:
    xss = (
        '<UserObject id="u" label="&lt;img src=x onerror=alert(1)&gt;" link="javascript:alert(1)">'
        '<mxCell style="" vertex="1" parent="1">'
        '<mxGeometry x="0" y="0" width="80" height="40" as="geometry"/>'
        "</mxCell></UserObject>"
    )
    found = codes(doc(xss))
    assert {"LR-S005", "LR-X001"} <= found


def test_diagonal_edge_and_shadow() -> None:
    text = doc(
        v("a", 40, 40, style="shadow=1;")
        + v("b", 240, 200)
        + e("e", "a", "b", "edgeStyle=none;exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    )
    found = {f.code for f in lint_text(text)}
    assert {"LR-C001", "LR-T005"} <= found


def test_edge_through_a_box() -> None:
    text = doc(
        v("a", 40, 40)
        + v("mid", 160, 40)
        + v("b", 280, 40)
        + e("e", "a", "b", "exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    )
    assert "LR-C005" in {f.code for f in lint_text(text)}


def test_compressed_input_is_decoded() -> None:
    inner = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>'
    enc = urllib.parse.quote(inner, safe="-_.!~*'()")
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    payload = base64.b64encode(co.compress(enc.encode()) + co.flush()).decode()
    findings = lint_text(f'<mxfile><diagram id="p" name="P">{payload}</diagram></mxfile>')
    assert [f.code for f in findings] == ["LR-S006"]


def tamper(xml: str, old: str, new: str) -> str:
    assert old in xml, old
    return xml.replace(old, new, 1)


def test_compiled_file_rules_fire_on_tampering() -> None:
    xml = build(example("architecture")).xml
    assert codes(xml) == set()
    off_grid = re.sub(
        r'(dd-id="gw"[^>]*><mxCell[^>]*><mxGeometry x=")(\d+)',
        lambda m: m.group(1) + str(int(m.group(2)) + 2),
        xml,
        count=1,
    )
    assert off_grid != xml
    assert "LR-G001" in codes(off_grid)
    off_palette = tamper(xml, "#bf4520", "#ff00ff")
    assert "LR-T001" in codes(off_palette)
    font = tamper(xml, "fontFamily=Geist Mono", "fontFamily=Comic Sans MS")
    assert "LR-T002" in codes(font)
    no_title = tamper(xml, 'dd-role="title"', 'dd-role="x"')
    assert "LR-S007" not in codes(no_title)  # still a title cell id
