"""Layered (Sugiyama-lite) layout engine on the 4px grid (PRD §11.2).

Works in abstract axes: `u` is the rank axis (x for LR, y for TB) and `v` is the
order axis inside a rank. Nodes are centred on multiples of 4 and every node size
is a multiple of 8, so every top-left corner lands on the 4px grid.
"""

from __future__ import annotations

from dataclasses import dataclass

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PNode, PZone
from ddraw.spec.model import Spec
from ddraw.text.measure import ceil4, round4, width

ZONE_PAD = 16
ZONE_LABEL = 32  # padding on the side that carries the zone eyebrow
STUB = 16


@dataclass
class Params:
    direction: str
    gap_v: int
    min_gap_u: int
    max_gap_u: int


def _ranks(spec: Spec) -> dict[str, int]:
    ids = [n.id for n in spec.nodes]
    given = {n.id: int(n.place["rank"]) for n in spec.nodes if "rank" in n.place}
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for e in spec.edges:
        if e.src != e.dst:
            succ[e.src].append(e.dst)
    # Break cycles: DFS in declaration order, drop back edges.
    state: dict[str, int] = {}
    dag: dict[str, list[str]] = {i: [] for i in ids}

    def visit(a: str) -> None:
        state[a] = 1
        for b in succ[a]:
            if state.get(b) == 1:
                continue  # back edge
            dag[a].append(b)
            if b not in state:
                visit(b)
        state[a] = 2

    for i in ids:
        if i not in state:
            visit(i)
    preds: dict[str, list[str]] = {i: [] for i in ids}
    for a, bs in dag.items():
        for b in bs:
            preds[b].append(a)
    rank: dict[str, int] = {}

    def r(a: str) -> int:
        if a in rank:
            return rank[a]
        if a in given:
            rank[a] = given[a]
            return rank[a]
        rank[a] = 0
        rank[a] = max((r(p) + 1 for p in preds[a]), default=0)
        return rank[a]

    for i in ids:
        r(i)
    # Compact: remove empty ranks.
    used = sorted(set(rank.values()))
    remap = {old: new for new, old in enumerate(used)}
    return {k: remap[v] for k, v in rank.items()}


def _orders(spec: Spec, rank: dict[str, int], bias: dict[str, float]) -> list[list[str]]:
    n_ranks = max(rank.values(), default=-1) + 1
    layers: list[list[str]] = [[] for _ in range(n_ranks)]
    for n in spec.nodes:
        layers[rank[n.id]].append(n.id)
    index = {n.id: n.index for n in spec.nodes}
    zone_of = {n.id: n.zone for n in spec.nodes}
    zone_index = {z.id: z.index for z in spec.zones}
    given = {n.id: int(n.place["order"]) for n in spec.nodes if "order" in n.place}
    nbrs: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    for e in spec.edges:
        if e.src != e.dst:
            nbrs[e.src].append(e.dst)
            nbrs[e.dst].append(e.src)

    def initial_key(i: str) -> tuple[float, float, float]:
        z = zone_of[i]
        return (
            given.get(i, 1000 + index[i]) if i in given else 1000.0,
            float(zone_index.get(z, -1)),
            float(index[i]),
        )

    for layer in layers:
        layer.sort(key=initial_key)

    def sweep(r: int, ref: int) -> None:
        pos = {node: k for k, node in enumerate(layers[ref])}
        current = {node: k for k, node in enumerate(layers[r])}

        def bary(i: str) -> float:
            ps = [pos[j] for j in nbrs[i] if j in pos]
            return (sum(ps) / len(ps) if ps else float(current[i])) + bias.get(i, 0.0) * 0.5

        if all(i in given for i in layers[r]):
            return
        blocks: dict[str, list[str]] = {}
        for i in layers[r]:
            key = zone_of[i] or f"__{i}"
            blocks.setdefault(key, []).append(i)
        ordered_blocks = sorted(
            blocks.values(),
            key=lambda b: (
                min(given.get(i, 999) for i in b),
                sum(bary(i) for i in b) / len(b),
                min(index[i] for i in b),
            ),
        )
        layers[r] = [
            i for b in ordered_blocks for i in sorted(b, key=lambda i: (given.get(i, 999), bary(i), index[i]))
        ]

    for _ in range(4):
        for r in range(1, n_ranks):
            sweep(r, r - 1)
        for r in range(n_ranks - 2, -1, -1):
            sweep(r, r + 1)
    return layers


def _pack(desired: list[float], seps: list[float]) -> list[float]:
    """Positions closest to `desired` with c[i+1] - c[i] >= seps[i] (average of two feasible passes)."""
    n = len(desired)
    if n == 0:
        return []
    fwd = list(desired)
    for i in range(1, n):
        fwd[i] = max(desired[i], fwd[i - 1] + seps[i - 1])
    bwd = list(desired)
    for i in range(n - 2, -1, -1):
        bwd[i] = min(desired[i], bwd[i + 1] - seps[i])
    return [(a + b) / 2 for a, b in zip(fwd, bwd, strict=True)]


def layout(
    spec: Spec,
    pnodes: dict[str, PNode],
    area: Box,
    direction: str,
    ramp: dict[str, int],
    fit: bool = False,
    bias: dict[str, float] | None = None,
) -> dict[str, PZone]:
    """`bias` nudges a node along the order axis by a fraction of its separation (type conventions)."""
    bias = bias or {}
    lr = direction in ("LR", "RL")
    rank = _ranks(spec)
    layers = _orders(spec, rank, bias)
    zone_of = {n.id: n.zone for n in spec.nodes}
    has_zones = bool(spec.zones)

    def su(i: str) -> float:
        b = pnodes[i].box
        return b.w if lr else b.h

    def sv(i: str) -> float:
        b = pnodes[i].box
        return b.h if lr else b.w

    # Gap between ranks: room for stubs, labels and zone padding.
    zone_need = (2 * ZONE_PAD + 16) if lr else (ZONE_PAD + ZONE_LABEL + 16)
    min_gap_u = ceil4(max(64 if lr else 48, zone_need if has_zones else 0))
    gap_v = max(32, int(ramp["minGap"]))

    band = [max((su(i) for i in layer), default=0.0) for layer in layers]
    total_u_nodes = sum(band)
    n_ranks = len(layers)
    avail_u = (
        (area.w if lr else area.h)
        - (2 * ZONE_PAD if has_zones else 0)
        - (ZONE_LABEL if has_zones and not lr else 0)
    )
    max_gap_u = 160 if lr else 96
    # Each rank boundary needs one 12px track per edge that jogs across it.
    crossing = [0] * max(0, n_ranks - 1)
    side_exit = ("top", "bottom") if lr else ("left", "right")
    for e in spec.edges:
        if e.from_side in side_exit or e.to_side in side_exit:
            continue  # leaves or enters sideways: no horizontal jog inside the rank gap
        lo, hi = sorted((rank[e.src], rank[e.dst]))
        for r in range(lo, hi):
            crossing[r] += 1
    # A labelled edge needs its label width (plus clearance) inside every gap it can be labelled in.
    label_need = [0.0] * max(0, n_ranks - 1)
    for e in spec.edges:
        if not e.label or e.src == e.dst:
            continue
        lo, hi = sorted((rank[e.src], rank[e.dst]))
        lw = width(e.label, ramp["arrow"], "mono", 0.06) + 8
        for r in range(lo, hi):
            label_need[r] = max(label_need[r], (lw + 44) if lr else 48)
    need = [
        ceil4(max(min_gap_u, label_need[r], 2 * STUB + 16 + 12 * max(0, k - 1)))
        for r, k in enumerate(crossing)
    ]
    gaps = list(need)
    if n_ranks > 1 and not fit:
        # Start from each gap's minimum, then spread the leftover space evenly (capped).
        leftover = avail_u - total_u_nodes - sum(gaps)
        if leftover > 0:
            extra = leftover / (n_ranks - 1)
            gaps = [max(g, min(max_gap_u, (int(g + extra) // 4) * 4)) for g in gaps]

    # u centres.
    u_center: dict[str, float] = {}
    cursor = 0.0
    for r, layer in enumerate(layers):
        for i in layer:
            u_center[i] = cursor + band[r] / 2
        cursor += band[r] + (gaps[r] if r < len(gaps) else 0)

    # v separations between neighbours inside a rank.
    def sep(a: str, b: str) -> float:
        base = (sv(a) + sv(b)) / 2 + gap_v
        if zone_of[a] != zone_of[b]:
            after = ZONE_PAD if zone_of[a] else 0
            before = (ZONE_LABEL if lr else ZONE_PAD) if zone_of[b] else 0
            base += after + before + (16 if zone_of[a] and zone_of[b] else 0)
        return base

    v_center: dict[str, float] = {}
    for layer in layers:
        c = 0.0
        for k, i in enumerate(layer):
            if k:
                c += sep(layer[k - 1], i)
            v_center[i] = c
        mid = (v_center[layer[0]] + v_center[layer[-1]]) / 2 if layer else 0
        for i in layer:
            v_center[i] -= mid

    nbr_prev: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    nbr_next: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    for e in spec.edges:
        if e.src == e.dst:
            continue
        a, b = (e.src, e.dst) if rank[e.src] <= rank[e.dst] else (e.dst, e.src)
        if rank[a] != rank[b]:
            nbr_prev[b].append(a)
            nbr_next[a].append(b)

    max_sv = max((sv(i) for i in pnodes), default=0.0)

    def shift(i: str) -> float:
        # Far enough that a biased node clears an unbiased sibling aligned with the shared parent.
        return bias.get(i, 0.0) * ceil4(sv(i) / 2 + max_sv / 2 + gap_v + 16)

    def settle(layer: list[str], nbr: dict[str, list[str]], down: bool) -> None:
        desired = []
        for i in layer:
            ps = nbr[i]
            if down:
                base = sum(v_center[p] for p in ps) / len(ps) if ps else v_center[i]
                desired.append(base + (shift(i) if ps else 0.0))
            else:
                desired.append(sum(v_center[p] - shift(p) for p in ps) / len(ps) if ps else v_center[i])
        seps = [sep(layer[k], layer[k + 1]) for k in range(len(layer) - 1)]
        for i, c in zip(layer, _pack(desired, seps), strict=True):
            v_center[i] = c

    for _ in range(3):
        for r in range(1, n_ranks):
            settle(layers[r], nbr_prev, True)
        for r in range(n_ranks - 2, -1, -1):
            settle(layers[r], nbr_next, False)
    for r in range(1, n_ranks):
        settle(layers[r], nbr_prev, True)
    for layer in layers:
        # Snap after settling; keep separations by pushing forward.
        prev = None
        for i in layer:
            c = round4(v_center[i])
            if prev is not None:
                c = max(c, prev + ceil4(sep(layer[layer.index(i) - 1], i)))
            v_center[i] = c
            prev = c

    for i, pn in pnodes.items():
        w, h = pn.box.w, pn.box.h
        cu, cv = round4(u_center[i]), v_center[i]
        if lr:
            pn.box = Box(cu - w / 2, cv - h / 2, w, h)
        else:
            pn.box = Box(cv - w / 2, cu - h / 2, w, h)
    if direction in ("RL", "BT"):
        for pn in pnodes.values():
            if lr:
                pn.box = Box(-pn.box.right, pn.box.y, pn.box.w, pn.box.h)
            else:
                pn.box = Box(pn.box.x, -pn.box.bottom, pn.box.w, pn.box.h)

    zones = build_zones(spec, pnodes, lr)
    # Centre the whole drawing in the area.
    boxes = [pn.box for pn in pnodes.values()] + [z.box for z in zones.values()]
    bbox = boxes[0]
    for other in boxes[1:]:
        bbox = bbox.union(other)
    dx = round4(area.x + (area.w - bbox.w) / 2 - bbox.x) if not fit else round4(area.x - bbox.x)
    dy = round4(area.y + (area.h - bbox.h) / 2 - bbox.y) if not fit else round4(area.y - bbox.y)
    for pn in pnodes.values():
        pn.box = pn.box.moved(dx, dy)
    for z in zones.values():
        z.box = z.box.moved(dx, dy)
    for n in spec.nodes:
        if n.pin:
            cur = pnodes[n.id].box
            pnodes[n.id].box = Box(
                round4(n.pin["x"]), round4(n.pin["y"]), n.pin.get("w") or cur.w, n.pin.get("h") or cur.h
            )
    if not fit and (bbox.w > area.w + 0.5 or bbox.h > area.h + 0.5):
        raise DDError(
            [
                Finding(
                    "LAYOUT-001",
                    f"diagram needs {bbox.w:.0f}×{bbox.h:.0f}px but the {spec.size} content area "
                    f"is {area.w:.0f}×{area.h:.0f}",
                    pointer="/size",
                    fix="use a larger size preset (doc-wide, slide-16x9, fit), switch direction, "
                    "lower the detail, or split",
                )
            ]
        )
    check_zone_overlap(zones, pnodes)
    return zones


def build_zones(spec: Spec, pnodes: dict[str, PNode], lr: bool) -> dict[str, PZone]:
    zones: dict[str, PZone] = {}
    children: dict[str, list[str]] = {z.id: [] for z in spec.zones}
    for z in spec.zones:
        if z.parent:
            children[z.parent].append(z.id)

    def build(zid: str, depth: int) -> Box | None:
        z = next(z for z in spec.zones if z.id == zid)
        boxes = [pnodes[n.id].box for n in spec.nodes if n.zone == zid]
        for c in children[zid]:
            cb = build(c, depth + 1)
            if cb:
                boxes.append(cb)
        if not boxes:
            return None
        b = boxes[0]
        for o in boxes[1:]:
            b = b.union(o)
        zb = Box(b.x - ZONE_PAD, b.y - ZONE_LABEL, b.w + 2 * ZONE_PAD, b.h + ZONE_LABEL + ZONE_PAD)
        zones[zid] = PZone(zone=z, box=zb, depth=depth)
        return zb

    for z in spec.zones:
        if not z.parent and z.id not in zones:
            build(z.id, 0)
    return zones


def check_zone_overlap(zones: dict[str, PZone], pnodes: dict[str, PNode]) -> None:
    findings: list[Finding] = []
    items = list(zones.values())
    for a_i, a in enumerate(items):
        for b in items[a_i + 1 :]:
            nested = a.box.contains(b.box) or b.box.contains(a.box)
            if not nested and a.box.intersects(b.box):
                findings.append(
                    Finding(
                        "LAYOUT-002",
                        f"zones {a.zone.id!r} and {b.zone.id!r} overlap",
                        pointer="/zones",
                        fix="give the members of each zone distinct place.rank values, or merge the zones",
                    )
                )
        for pn in pnodes.values():
            if (
                pn.node.zone != a.zone.id
                and not _inside_descendant(pn.node.zone, a.zone.id, zones)
                and a.box.intersects(pn.box)
            ):
                findings.append(
                    Finding(
                        "LAYOUT-003",
                        f"node {pn.id!r} sits inside zone {a.zone.id!r} but is not a member",
                        pointer=f"/nodes/{pn.node.index}/zone",
                        fix=f'add "zone": "{a.zone.id}" or move the node to another rank',
                    )
                )
    if findings:
        raise DDError(findings)


def _inside_descendant(node_zone: str, zone_id: str, zones: dict[str, PZone]) -> bool:
    z = node_zone
    while z:
        if z == zone_id:
            return True
        z = zones[z].zone.parent if z in zones else ""
    return False
