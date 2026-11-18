"""Bands engine: full-width stacked rows in spec order (layer stacks; PRD §11.2)."""

from __future__ import annotations

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PNode
from ddraw.spec.model import Spec
from ddraw.text.measure import round4

MAX_WIDTH = 800
GAP = 8


def layout(spec: Spec, pnodes: dict[str, PNode], area: Box, ramp: dict[str, int], fit: bool) -> None:
    n = len(spec.nodes)
    h = max(56, int(ramp["minNodeHeight"]) + 8)
    w = min(MAX_WIDTH, int(area.w)) // 8 * 8 if not fit else MAX_WIDTH
    need = max((pn.box.w for pn in pnodes.values()), default=0)
    if need > w:
        raise DDError([Finding("TEXT-001", "a layer label does not fit the band", pointer="/nodes")])
    total = n * h + max(0, n - 1) * GAP
    if not fit and total > area.h + 0.5:
        raise DDError(
            [
                Finding(
                    "LAYOUT-001",
                    f"{n} layers need {total}px; the {spec.size} content area is {area.h:.0f}px tall",
                    pointer="/size",
                    fix="use a taller preset (slide-4x3, social-square, print) or fewer layers",
                )
            ]
        )
    x = round4(area.x + (area.w - w) / 2) if not fit else round4(area.x)
    y = round4(area.y + (area.h - total) / 2) if not fit else round4(area.y)
    for node in spec.nodes:
        pnodes[node.id].box = Box(x, y, w, h)
        y += h + GAP
