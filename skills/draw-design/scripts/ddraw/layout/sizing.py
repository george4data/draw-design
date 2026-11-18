"""Node sizing from the text width budget (PRD §11.6)."""

from __future__ import annotations

from typing import Any

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PNode
from ddraw.registry import presets
from ddraw.spec.model import Node
from ddraw.text.measure import width

PAD = 16
TREATMENT_BY_ROLE = {
    "backend": "backend",
    "step": "backend",
    "start": "backend",
    "end": "backend",
    "decision": "backend",
    "state": "backend",
    "initial": "backend",
    "final": "backend",
    "layer": "backend",
    "store": "store",
    "external": "external",
    "input": "input",
    "optional": "optional",
    "security": "security",
}
SHAPE_BY_ROLE = {
    "start": "pill",
    "end": "pill",
    "decision": "rhombus",
    "initial": "dot",
    "final": "ring",
    "state": "state",
}
MARKERS = {"dot": 24, "ring": 32}


def widths() -> list[int]:
    return [w for w in presets()["nodeWidths"] if w % 8 == 0]


def pick(size: float, allowed: list[int]) -> int | None:
    for a in allowed:
        if a >= size:
            return a
    return None


def text_need(n: Node, ramp: dict[str, Any]) -> float:
    name = width(n.label, ramp["node"], "sans")
    sub = width(n.sublabel, ramp["sublabel"], "mono") if n.sublabel else 0.0
    return max(name, sub)


def size_nodes(nodes: list[Node], ramp: dict[str, Any]) -> dict[str, PNode]:
    """Uniform width and height for box-like nodes; rhombi sized on their own."""
    allowed = widths()
    findings: list[Finding] = []
    box_need = 0.0
    any_tag = any(n.tag for n in nodes)
    for n in nodes:
        if SHAPE_BY_ROLE.get(n.role) not in ("rhombus", "dot", "ring"):
            box_need = max(box_need, text_need(n, ramp) + 2 * PAD)
    w = pick(box_need, allowed)
    if w is None:
        findings.append(
            Finding(
                "TEXT-001",
                f"a label needs {box_need:.0f}px; the widest node is 320px",
                pointer="/nodes",
                fix="shorten the longest label or sublabel",
            )
        )
        w = allowed[-1]
    h = int(ramp["minNodeHeight"]) + (8 if any_tag else 0)
    out: dict[str, PNode] = {}
    for n in nodes:
        shape = SHAPE_BY_ROLE.get(n.role, "box")
        treatment = "focal" if n.focal else TREATMENT_BY_ROLE.get(n.role, "backend")
        if shape in MARKERS:
            box = Box(0, 0, MARKERS[shape], MARKERS[shape])
        elif shape == "rhombus":
            need = text_need(n, ramp) * 1.5 + 16
            rw = int(-(-need // 8) * 8) if need <= 320 else None
            if rw is None:
                findings.append(
                    Finding(
                        "TEXT-001",
                        f"decision label {n.label!r} is too long for a diamond",
                        pointer=f"/nodes/{n.index}/label",
                        fix="phrase it as a short question",
                    )
                )
                rw = allowed[-1]
            box = Box(0, 0, max(rw, 120), max(h + 24, 72))
        elif shape == "pill":
            box = Box(0, 0, w, h - 8 if h > 48 else 40)
        else:
            box = Box(0, 0, w, h)
        out[n.id] = PNode(node=n, box=box, shape=shape, treatment=treatment)
    if findings:
        raise DDError(findings)
    return out
