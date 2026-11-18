"""Tidy tree engine (PRD §11.2): leaves in declaration order, each parent centred over its children."""

from __future__ import annotations

import itertools

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PNode
from ddraw.spec.model import Spec
from ddraw.text.measure import ceil4, round4

LEVEL_GAP = 64
SIBLING_GAP = 32
SUBTREE_GAP = 48


def layout(spec: Spec, pnodes: dict[str, PNode], area: Box, direction: str, fit: bool) -> None:
    lr = direction in ("LR", "RL")
    children: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    has_parent: set[str] = set()
    for e in sorted(spec.edges, key=lambda e: e.index):
        if e.dst not in has_parent:
            children[e.src].append(e.dst)
            has_parent.add(e.dst)
    roots = [n.id for n in spec.nodes if n.id not in has_parent]

    def su(i: str) -> float:  # size along the level axis
        return pnodes[i].box.w if lr else pnodes[i].box.h

    def sv(i: str) -> float:  # size along the sibling axis
        return pnodes[i].box.h if lr else pnodes[i].box.w

    depth: dict[str, int] = {}

    def set_depth(i: str, d: int) -> None:
        depth[i] = d
        for c in children[i]:
            set_depth(c, d + 1)

    for r in roots:
        set_depth(r, 0)
    levels = max(depth.values(), default=0) + 1
    band = [max((su(i) for i in depth if depth[i] == lv), default=0.0) for lv in range(levels)]

    v_center: dict[str, float] = {}
    cursor = [0.0]
    last_leaf: list[str | None] = [None]

    def place(i: str) -> None:
        kids = children[i]
        if not kids:
            prev = last_leaf[0]
            if prev is not None:
                same_parent = any(prev in children[p] and i in children[p] for p in children)
                cursor[0] += sv(prev) / 2 + (SIBLING_GAP if same_parent else SUBTREE_GAP) + sv(i) / 2
            v_center[i] = cursor[0]
            last_leaf[0] = i
            return
        for c in kids:
            place(c)
        v_center[i] = (v_center[kids[0]] + v_center[kids[-1]]) / 2

    for r in roots:
        place(r)
    # Parents wider than their subtree can collide with neighbours: push later subtrees along.
    for lv in range(levels):
        row = sorted((i for i in depth if depth[i] == lv), key=lambda i: v_center[i])
        for a, b in itertools.pairwise(row):
            need = sv(a) / 2 + SIBLING_GAP + sv(b) / 2
            if v_center[b] - v_center[a] < need:
                shift = need - (v_center[b] - v_center[a])
                _shift_subtree(b, shift, children, v_center, row, depth)
    u_start = [0.0]
    for lv in range(1, levels):
        u_start.append(u_start[-1] + band[lv - 1] + LEVEL_GAP)
    for i, pn in pnodes.items():
        cu = u_start[depth[i]] + band[depth[i]] / 2
        cv = v_center[i]
        w, h = pn.box.w, pn.box.h
        pn.box = Box(cu - w / 2, cv - h / 2, w, h) if lr else Box(cv - w / 2, cu - h / 2, w, h)
    boxes = [pn.box for pn in pnodes.values()]
    bbox = boxes[0]
    for other in boxes[1:]:
        bbox = bbox.union(other)
    dx = round4(area.x - bbox.x) if fit else round4(area.x + (area.w - bbox.w) / 2 - bbox.x)
    dy = round4(area.y - bbox.y) if fit else round4(area.y + (area.h - bbox.h) / 2 - bbox.y)
    for pn in pnodes.values():
        cur = pn.box
        pn.box = Box(round4(cur.x + dx), round4(cur.y + dy), cur.w, cur.h)
    if not fit and (bbox.w > area.w + 0.5 or bbox.h > area.h + 0.5):
        raise DDError(
            [
                Finding(
                    "LAYOUT-001",
                    f"tree needs {ceil4(bbox.w)}×{ceil4(bbox.h)}px but the {spec.size} content area is "
                    f"{area.w:.0f}×{area.h:.0f}",
                    pointer="/size",
                    fix="use a wider preset, switch direction (LR), or split into overview + subtrees",
                )
            ]
        )


def _shift_subtree(
    i: str,
    shift: float,
    children: dict[str, list[str]],
    v: dict[str, float],
    row: list[str],
    depth: dict[str, int],
) -> None:
    # Shift this node, its subtree and every later node on the same level (and their subtrees).
    later = row[row.index(i) :]
    seen: set[str] = set()

    def move(n: str) -> None:
        if n in seen:
            return
        seen.add(n)
        v[n] += shift
        for c in children[n]:
            move(c)

    for n in later:
        move(n)
