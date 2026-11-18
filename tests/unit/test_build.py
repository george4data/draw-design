from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from ddraw.pipeline import build
from helpers import GOLDEN, example, shipped_examples


@pytest.mark.parametrize("name", shipped_examples())
def test_example_builds_lint_clean(name: str) -> None:
    result = build(example(name))
    errors = [f.human() for f in result.findings if f.severity in ("error", "warn")]
    assert errors == []


@pytest.mark.parametrize("name", shipped_examples())
def test_build_is_deterministic(name: str) -> None:
    assert build(example(name)).xml == build(example(name)).xml


@pytest.mark.parametrize("name", shipped_examples())
def test_golden(name: str, update_golden: bool) -> None:
    xml = build(example(name)).xml
    path = GOLDEN / f"{name}.drawio"
    if update_golden or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding="utf-8")
    assert xml == path.read_text(encoding="utf-8"), "golden changed: rerun with --update-golden and justify"


def test_output_structure() -> None:
    xml = build(example("architecture")).xml
    root = ET.fromstring(xml)
    assert root.tag == "mxfile" and root.get("compressed") == "false"
    cells = root.find("diagram/mxGraphModel/root")
    assert cells is not None
    ids = [c.get("id") for c in cells]
    assert ids[:3] == ["0", "frame-layer", "1"]
    assert len(ids) == len(set(ids))
    user_objects = cells.findall("UserObject")
    assert all(u.find("mxCell") is not None and u.find("mxCell").get("id") is None for u in user_objects)  # type: ignore[union-attr]
    edges = [u for u in user_objects if u.get("dd-role") == "edge"]
    assert len(edges) == 7
    # Edges are written before nodes so they paint behind boxes.
    first_node = next(i for i, u in enumerate(user_objects) if u.get("dd-id") == "web")
    last_edge = max(i for i, u in enumerate(user_objects) if u.get("dd-role") == "edge")
    assert last_edge < first_node


def test_no_adaptive_emits_plain_hex() -> None:
    xml = build(example("architecture"), adaptive=False).xml
    assert "light-dark(" not in xml


def test_dark_variant_is_a_fixed_dark_rendering() -> None:
    data = example("architecture")
    data["variant"] = "dark"
    xml = build(data).xml
    assert 'background="#2d3142"' in xml and "light-dark(" not in xml


def test_over_capacity_reports_layout_error() -> None:
    from ddraw.errors import DDError

    data = example("architecture")
    data["size"] = "social-square"
    data["direction"] = "LR"
    data["nodes"][3]["label"] = "Order management service"
    with pytest.raises(DDError) as exc:
        build(data)
    assert exc.value.findings[0].code in ("LAYOUT-001", "TEXT-001")


def test_fit_preset_grows_to_content() -> None:
    data = example("architecture")
    data["size"] = "fit"
    result = build(data)
    assert result.ok, [f.human() for f in result.findings]
    assert result.page.frame.w % 4 == 0 and result.page.frame.h % 4 == 0
