"""Lifelines engine for sequence diagrams (PRD §11.2, §12.4 #3).

x = participant column, y = message index. Participants are draw.io `umlLifeline` shapes;
messages are edges attached to them at computed heights; activations are nested children.
"""

from __future__ import annotations

from typing import Any

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, ExtraCell, Page, Port
from ddraw.text.measure import ceil4, round4, width

FIRST_GAP = 32  # header bottom → first message
STEP = 36  # between messages
SELF_EXTRA = 24  # a self-message needs its loop height
FRAG_TOP = 48  # room for a fragment tab and guard above its first message
FRAG_BOTTOM = 16
ELSE_GAP = 24
ACT_W = 8
LOOP_W = 32
LABEL_GAP = 8


def _label_w(text: str, ramp: dict[str, Any]) -> float:
    return width(text, ramp["arrow"], "mono", 0.06) + 8


def layout(page: Page, area: Box, fit: bool) -> None:
    spec, ramp = page.spec, page.ramp
    seq: dict[str, Any] = spec.raw["sequence"]
    parts = spec.nodes
    msgs = sorted(page.edges, key=lambda pe: pe.edge.index)
    col = {p.id: i for i, p in enumerate(parts)}
    head = next(iter(page.nodes.values())).box
    w_node, h_head = head.w, head.h
    for pn in page.nodes.values():
        pn.shape = "lifeline"

    # Column pitch: room for boxes and for each message label over the span it crosses.
    gaps = [w_node + 32.0] * max(0, len(parts) - 1)
    for pe in msgs:
        a, b = sorted((col[pe.edge.src], col[pe.edge.dst]))
        lw = _label_w(pe.edge.label, ramp) if pe.edge.label else 0.0
        if a == b:
            if a < len(gaps):
                gaps[a] = max(gaps[a], ACT_W + LOOP_W + LABEL_GAP + lw + 24)
            continue
        per = (lw + 48) / (b - a)
        for i in range(a, b):
            gaps[i] = max(gaps[i], per)
    centers = [0.0]
    for g in gaps:
        centers.append(centers[-1] + ceil4(g))

    # Vertical rhythm.
    frags: list[dict[str, Any]] = list(seq.get("fragments", []))
    starts: dict[int, int] = {}
    ends: dict[int, int] = {}
    elses = {int(f["elseAt"]) for f in frags if "elseAt" in f}
    for f in frags:
        starts[int(f["from"])] = starts.get(int(f["from"]), 0) + 1
        ends[int(f["to"])] = ends.get(int(f["to"]), 0) + 1
    y = h_head + FIRST_GAP
    msg_y: dict[int, float] = {}
    for k, pe in enumerate(msgs, start=1):
        y += FRAG_TOP * starts.get(k, 0)
        if k in elses:
            y += ELSE_GAP
        msg_y[k] = y
        y += STEP + (SELF_EXTRA if pe.edge.src == pe.edge.dst else 0)
        y += FRAG_BOTTOM * ends.get(k, 0)
    life_h = ceil4(y)
    total_w = centers[-1] + w_node
    if not fit and (total_w > area.w + 0.5 or life_h > area.h + 0.5):
        raise DDError(
            [
                Finding(
                    "LAYOUT-001",
                    f"sequence needs {ceil4(total_w)}×{life_h}px but the {spec.size} content area is "
                    f"{area.w:.0f}×{area.h:.0f}",
                    pointer="/size",
                    fix="use doc-wide or a slide preset, shorten labels, or split the flow into two diagrams",
                )
            ]
        )
    x0 = round4(area.x + (area.w - total_w) / 2) if not fit else round4(area.x)
    y0 = round4(area.y + (area.h - life_h) / 2) if not fit else round4(area.y)
    cx = {p.id: x0 + w_node / 2 + centers[i] for i, p in enumerate(parts)}
    for p in parts:
        page.nodes[p.id].box = Box(cx[p.id] - w_node / 2, y0, w_node, life_h)

    # Activations: callee is active from a sync call until the matching return.
    open_: dict[str, list[tuple[float, str]]] = {p.id: [] for p in parts}
    bars: list[tuple[str, float, float, int]] = []
    active_at: dict[tuple[str, int], int] = {}
    for k, pe in enumerate(msgs, start=1):
        e = pe.edge
        yy = y0 + msg_y[k]
        for pid in open_:
            active_at[(pid, k)] = len(open_[pid])
        if e.src == e.dst:
            continue
        if e.msg_kind == "sync":
            open_[e.dst].append((yy, e.src))
        elif e.msg_kind == "return" and open_[e.src]:
            start, _caller = open_[e.src].pop()
            bars.append((e.src, start, yy, len(open_[e.src])))
    last = y0 + life_h - 12
    for pid, stack in open_.items():
        while stack:
            start, _ = stack.pop()
            bars.append((pid, start, min(last, start + STEP), len(stack)))
    for n, (pid, start, end, depth) in enumerate(sorted(bars, key=lambda b: (b[0], b[1]))):
        lb = page.nodes[pid].box
        ax = round4(w_node / 2 - ACT_W / 2 + 4 * depth)
        top = round4(start - 4 - lb.y)
        bottom = ceil4(end + 4 - lb.y)
        page.extras.append(
            ExtraCell(f"act-{pid}-{n + 1}", "activation", Box(ax, top, ACT_W, bottom - top), parent=pid)
        )

    def is_active(pid: str, k: int, including_new: bool = False) -> bool:
        if active_at.get((pid, k), 0) > 0:
            return True
        e = msgs[k - 1].edge
        return including_new and e.msg_kind == "sync" and e.dst == pid

    # Messages.
    for k, pe in enumerate(msgs, start=1):
        e = pe.edge
        yy = y0 + msg_y[k]
        src_box, dst_box = page.nodes[e.src].box, page.nodes[e.dst].box
        if e.src == e.dst:
            x1 = cx[e.src] + (ACT_W / 2 if is_active(e.src, k) else 0)
            pe.path = [
                (x1, yy),
                (x1 + LOOP_W, yy),
                (x1 + LOOP_W, yy + SELF_EXTRA - 8),
                (x1, yy + SELF_EXTRA - 8),
            ]
            pe.src_port = Port("right", x1, yy, (x1 - src_box.x) / src_box.w, (yy - src_box.y) / src_box.h)
            pe.dst_port = Port(
                "right",
                x1,
                yy + SELF_EXTRA - 8,
                (x1 - src_box.x) / src_box.w,
                (yy + SELF_EXTRA - 8 - src_box.y) / src_box.h,
            )
            if e.label:
                lw = _label_w(e.label, ramp)
                total = 2 * LOOP_W + SELF_EXTRA - 8
                pe.label_param = round(2 * (LOOP_W + (SELF_EXTRA - 8) / 2) / total - 1, 4)
                pe.label_offset = (LABEL_GAP + lw / 2, 0.0)
                pe.label_box = Box(x1 + LOOP_W + LABEL_GAP, yy + (SELF_EXTRA - 8) / 2 - 6, lw, 12)
            continue
        sign = 1.0 if cx[e.dst] > cx[e.src] else -1.0
        x1 = cx[e.src] + (sign * ACT_W / 2 if is_active(e.src, k) else 0.0)
        x2 = cx[e.dst] - (sign * ACT_W / 2 if is_active(e.dst, k, including_new=True) else 0.0)
        pe.path = [(x1, yy), (x2, yy)]
        side_s = "right" if sign > 0 else "left"
        side_d = "left" if sign > 0 else "right"
        pe.src_port = Port(side_s, x1, yy, (x1 - src_box.x) / src_box.w, (yy - src_box.y) / src_box.h)
        pe.dst_port = Port(side_d, x2, yy, (x2 - dst_box.x) / dst_box.w, (yy - dst_box.y) / dst_box.h)
        if e.label:
            lw = _label_w(e.label, ramp)
            pe.label_param = 0.0
            pe.label_offset = (0.0, -(LABEL_GAP + 6))
            pe.label_box = Box((x1 + x2) / 2 - lw / 2, yy - LABEL_GAP - 12, lw, 12)

    # Fragments: frame, operator tab, guard text, optional else divider.
    for n, f in enumerate(frags):
        lo, hi = int(f["from"]), int(f["to"])
        involved = {p for pe in msgs[lo - 1 : hi] for p in (pe.edge.src, pe.edge.dst)}
        nest = sum(1 for g in frags if g is not f and int(g["from"]) <= lo and hi <= int(g["to"]))
        xs = [cx[p] for p in involved]
        left = round4(min(xs) - 56 - 8 * nest - (w_node / 2 if len(involved) == 1 else 0))
        right = ceil4(
            max(xs)
            + 24
            + 8 * nest
            + (
                LOOP_W + 40
                if any(msgs[k - 1].edge.src == msgs[k - 1].edge.dst for k in range(lo, hi + 1))
                else 0
            )
        )
        top = round4(y0 + msg_y[lo] - FRAG_TOP + 4 + 8 * nest - (ELSE_GAP if lo in elses else 0))
        last_self = msgs[hi - 1].edge.src == msgs[hi - 1].edge.dst
        bottom = ceil4(y0 + msg_y[hi] + (SELF_EXTRA if last_self else 0) + FRAG_BOTTOM - 4 - 8 * nest)
        frame = Box(left, top, right - left, bottom - top)
        page.extras.append(ExtraCell(f"frag-{n + 1}", "fragment", frame, label=f["kind"]))
        if f.get("label"):
            text = f"[{f['label']}]"
            tw = ceil4(width(text, 8, "mono") + 4)
            gx = max(left + 56, round4(min(xs) + ACT_W))
            page.extras.append(
                ExtraCell(f"frag-{n + 1}-guard", "guard", Box(gx, top + 4, tw, 16), label=text)
            )
        if "elseAt" in f:
            ey = round4(y0 + msg_y[int(f["elseAt"])] - ELSE_GAP)
            page.extras.append(ExtraCell(f"frag-{n + 1}-else", "else", Box(left, ey - 4, right - left, 8)))
            if f.get("elseLabel"):
                text = f"[{f['elseLabel']}]"
                tw = ceil4(width(text, 8, "mono") + 4)
                page.extras.append(
                    ExtraCell(f"frag-{n + 1}-else-guard", "guard", Box(left + 8, ey + 4, tw, 16), label=text)
                )
    page.edges_first = False
    page.prerouted = True
