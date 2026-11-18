"""Lanes engine (PRD §11.2): one horizontal lane per actor, steps left to right."""

from __future__ import annotations

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PNode, PZone
from ddraw.layout.layered import _ranks
from ddraw.spec.model import Spec
from ddraw.text.measure import ceil4, round4, width

LANE_PAD = 24
LABEL_PAD = 24
MIN_GAP = 56
MAX_GAP = 120
RIGHT_PAD = 24


def _steps(spec: Spec) -> dict[str, int]:
    """Columns advance for work inside a lane; a handoff to another lane drops into the same column."""
    rank = _ranks(spec)
    lane = {n.id: n.zone for n in spec.nodes}
    preds: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    for e in spec.edges:
        if e.src != e.dst and rank[e.src] < rank[e.dst]:
            preds[e.dst].append(e.src)
    step: dict[str, int] = {}
    taken: set[tuple[str, int]] = set()
    for n in sorted(spec.nodes, key=lambda n: (rank[n.id], n.index)):
        if "step" in n.place:
            s = int(n.place["step"])
        else:
            s = max(
                (step[p] + (0 if lane[p] != lane[n.id] else 1) for p in preds[n.id] if p in step), default=0
            )
            while (lane[n.id], s) in taken:
                s += 1
        step[n.id] = s
        taken.add((lane[n.id], s))
    return step


def layout(
    spec: Spec, pnodes: dict[str, PNode], area: Box, ramp: dict[str, int], fit: bool
) -> dict[str, PZone]:
    lanes = spec.zones
    findings: list[Finding] = []
    for i, n in enumerate(spec.nodes):
        if not n.zone:
            findings.append(
                Finding(
                    "LR-Y-swimlane-001",
                    f"node {n.id!r} has no lane",
                    pointer=f"/nodes/{i}/zone",
                    fix='set "zone" to the id of the lane (actor) that performs the step',
                )
            )
    if findings:
        raise DDError(findings)
    step = _steps(spec)
    seen: dict[tuple[str, int], str] = {}
    for i, n in enumerate(spec.nodes):
        key = (n.zone, step[n.id])
        if key in seen:
            findings.append(
                Finding(
                    "LAYOUT-004",
                    f"{n.id!r} and {seen[key]!r} fall on the same step in lane {n.zone!r}",
                    pointer=f"/nodes/{i}/place",
                    fix="give one of them a different place.step",
                )
            )
        seen[key] = n.id
    if findings:
        raise DDError(findings)
    n_steps = max(step.values(), default=0) + 1
    w_node = max((pn.box.w for pn in pnodes.values()), default=120.0)
    h_node = max((pn.box.h for pn in pnodes.values()), default=48.0)
    label_col = ceil4(
        max(112.0, max((width(z.label.upper(), 8, "mono", 0.14) for z in lanes), default=0.0) + 2 * LABEL_PAD)
    )
    # Edge labels between steps need room on the horizontal run.
    need = [float(MIN_GAP)] * max(0, n_steps - 1)
    for e in spec.edges:
        if e.label:
            lo, hi = sorted((step[e.src], step[e.dst]))
            lw = width(e.label, ramp["arrow"], "mono", 0.06) + 8
            for s in range(lo, hi):
                need[s] = max(need[s], lw + 44)
    gaps = [ceil4(g) for g in need]
    base_w = label_col + n_steps * w_node + sum(gaps) + RIGHT_PAD
    if not fit and n_steps > 1 and area.w > base_w:
        extra = (area.w - base_w) / (n_steps - 1)
        gaps = [max(g, min(MAX_GAP, (int(g + extra) // 4) * 4)) for g in gaps]
    total_w = label_col + n_steps * w_node + sum(gaps) + RIGHT_PAD
    lane_h = ceil4(h_node + 2 * LANE_PAD)
    total_h = lane_h * len(lanes)
    if not fit and (total_w > area.w + 0.5 or total_h > area.h + 0.5):
        raise DDError(
            [
                Finding(
                    "LAYOUT-001",
                    f"swimlane needs {ceil4(total_w)}×{total_h}px but the {spec.size} content area is "
                    f"{area.w:.0f}×{area.h:.0f}",
                    pointer="/size",
                    fix="use doc-wide or a slide preset, merge steps, or split the process",
                )
            ]
        )
    x0 = round4(area.x + (area.w - total_w) / 2) if not fit else round4(area.x)
    y0 = round4(area.y + (area.h - total_h) / 2) if not fit else round4(area.y)
    step_x = [float(x0 + label_col)]
    for g in gaps:
        step_x.append(step_x[-1] + w_node + g)
    zones: dict[str, PZone] = {}
    for i, z in enumerate(lanes):
        zones[z.id] = PZone(zone=z, box=Box(x0, y0 + i * lane_h, ceil4(total_w), lane_h))
    for n in spec.nodes:
        pn = pnodes[n.id]
        lane = zones[n.zone].box
        cx = step_x[step[n.id]] + w_node / 2
        cy = lane.y + lane_h / 2
        pn.box = Box(round4(cx - pn.box.w / 2), round4(cy - pn.box.h / 2), pn.box.w, pn.box.h)
    return zones
