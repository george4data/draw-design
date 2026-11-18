"""Orthogonal connector router (PRD §11.3–11.5).

* Ports: connectors on one side of a box fan out at L*k/(N+1).
* Paths: A* over a sparse orthogonal grid built from obstacle edges and channel
  centres; cost = length + bend penalty + crossing penalty, with collinear overlap
  with already-routed edges and transit through non-endpoint boxes forbidden.
* Labels: placed on the longest segment through open canvas, 8px off the stroke.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, PEdge, PNode, Point, Port
from ddraw.spec.model import Edge
from ddraw.text.measure import width

STUB = 16
CLEAR = 10  # clearance between a path and a non-endpoint box
BEND = 40.0
CROSS = 80.0
PARALLEL = 12  # minimum distance between parallel segments of different edges
LABEL_GAP = 8
LABEL_H = 12
KIND_RANK = {"accent": 0, "link": 1, "default": 2, "async": 3, "return": 4}
NORMAL = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}


@dataclass
class Seg:
    x1: float
    y1: float
    x2: float
    y2: float
    edge: str

    @property
    def horizontal(self) -> bool:
        return self.y1 == self.y2


def _sides(a: Box, b: Box, e: Edge, direction: str) -> tuple[str, str]:
    if e.from_side and e.to_side:
        return e.from_side, e.to_side
    lr = direction in ("LR", "RL")
    if b.x >= a.right + 8:
        s = ("right", "left")
    elif b.right <= a.x - 8:
        s = ("left", "right")
    elif b.y >= a.bottom + 8:
        s = ("bottom", "top")
    elif b.bottom <= a.y - 8:
        s = ("top", "bottom")
    else:
        s = ("right", "left") if lr else ("bottom", "top")
    # In TB flows prefer vertical ports when the target is mostly below/above.
    if not lr and s[0] in ("left", "right") and (b.y >= a.bottom or b.bottom <= a.y):
        s = ("bottom", "top") if b.y >= a.bottom else ("top", "bottom")
    return e.from_side or s[0], e.to_side or s[1]


def _port(box: Box, side: str, frac: float) -> Port:
    if side == "top":
        return Port(side, round(box.x + box.w * frac), box.y, frac, 0.0)
    if side == "bottom":
        return Port(side, round(box.x + box.w * frac), box.bottom, frac, 1.0)
    if side == "left":
        return Port(side, box.x, round(box.y + box.h * frac), 0.0, frac)
    return Port(side, box.right, round(box.y + box.h * frac), 1.0, frac)


def _assign_ports(edges: list[PEdge], nodes: dict[str, PNode], direction: str) -> None:
    single = {"rhombus", "ellipse", "pill", "dot", "ring"}
    sides: dict[tuple[str, str], list[tuple[PEdge, bool]]] = {}
    for pe in edges:
        a, b = nodes[pe.edge.src], nodes[pe.edge.dst]
        s_src, s_dst = _sides(a.box, b.box, pe.edge, direction)
        sides.setdefault((a.id, s_src), []).append((pe, True))
        sides.setdefault((b.id, s_dst), []).append((pe, False))
    # Shapes with a single attach point per side spill extra connectors to free sides.
    for (nid, side), items in list(sides.items()):
        if nodes[nid].shape in single and len(items) > 1:
            free = [s for s in ("bottom", "right", "left", "top") if (nid, s) not in sides]
            for item in items[1:]:
                if not free:
                    break
                sides.setdefault((nid, free.pop(0)), []).append(item)
            sides[(nid, side)] = items[:1]
    for (nid, side), items in sides.items():
        box = nodes[nid].box
        horizontal_side = side in ("top", "bottom")

        def far(item: tuple[PEdge, bool], horizontal_side: bool = horizontal_side) -> float:
            pe, is_src = item
            other = nodes[pe.edge.dst if is_src else pe.edge.src].box
            return other.cx if horizontal_side else other.cy

        items.sort(key=lambda it: (far(it), it[0].edge.index))
        n = len(items)
        for k, (pe, is_src) in enumerate(items, start=1):
            port = _port(box, side, k / (n + 1))
            if is_src:
                pe.src_port = port
            else:
                pe.dst_port = port


class Grid:
    def __init__(self, xs: list[float], ys: list[float]) -> None:
        self.xs = sorted(set(xs))
        self.ys = sorted(set(ys))


def _coords(boxes: list[Box], extra_x: list[float], extra_y: list[float], frame: Box) -> Grid:
    xs: list[float] = list(extra_x)
    ys: list[float] = list(extra_y)
    for b in boxes:
        xs += [b.x - CLEAR - 6, b.right + CLEAR + 6]
        ys += [b.y - CLEAR - 6, b.bottom + CLEAR + 6]
    for vals, lo_hi in (
        (xs, sorted([b.x for b in boxes] + [b.right for b in boxes])),
        (ys, sorted([b.y for b in boxes] + [b.bottom for b in boxes])),
    ):
        for a, c in itertools.pairwise(lo_hi):
            if c - a > 2 * CLEAR:
                m = (a + c) / 2
                vals += [m, m - PARALLEL, m + PARALLEL, m - 2 * PARALLEL, m + 2 * PARALLEL]
    if boxes:
        lo_x, hi_x = min(b.x for b in boxes), max(b.right for b in boxes)
        lo_y, hi_y = min(b.y for b in boxes), max(b.bottom for b in boxes)
        for k in (1, 2, 3):
            xs += [lo_x - CLEAR - 6 - PARALLEL * k, hi_x + CLEAR + 6 + PARALLEL * k]
            ys += [lo_y - CLEAR - 6 - PARALLEL * k, hi_y + CLEAR + 6 + PARALLEL * k]
    xs = [round(x) for x in xs if frame.x <= x <= frame.right]
    ys = [round(y) for y in ys if frame.y <= y <= frame.bottom]
    return Grid(xs, ys)


def _seg_hits_box(x1: float, y1: float, x2: float, y2: float, b: Box) -> bool:
    lo_x, hi_x = min(x1, x2), max(x1, x2)
    lo_y, hi_y = min(y1, y2), max(y1, y2)
    return lo_x < b.right and hi_x > b.x and lo_y < b.bottom and hi_y > b.y


def _overlaps(s: Seg, x1: float, y1: float, x2: float, y2: float) -> bool:
    if y1 == y2 and s.horizontal and abs(s.y1 - y1) < PARALLEL:
        return min(max(s.x1, s.x2), max(x1, x2)) - max(min(s.x1, s.x2), min(x1, x2)) > 1
    if x1 == x2 and not s.horizontal and abs(s.x1 - x1) < PARALLEL:
        return min(max(s.y1, s.y2), max(y1, y2)) - max(min(s.y1, s.y2), min(y1, y2)) > 1
    return False


def _crosses(s: Seg, x1: float, y1: float, x2: float, y2: float) -> bool:
    if y1 == y2 and not s.horizontal:
        return min(x1, x2) < s.x1 < max(x1, x2) and min(s.y1, s.y2) < y1 < max(s.y1, s.y2)
    if x1 == x2 and s.horizontal:
        return min(y1, y2) < s.y1 < max(y1, y2) and min(s.x1, s.x2) < x1 < max(s.x1, s.x2)
    return False


def _astar(
    start: Point,
    sdir: tuple[int, int],
    goal: Point,
    gdir: tuple[int, int],
    grid: Grid,
    obstacles: list[Box],
    routed: list[Seg],
) -> list[Point] | None:
    xi = {x: i for i, x in enumerate(grid.xs)}
    yi = {y: i for i, y in enumerate(grid.ys)}
    if start[0] not in xi or start[1] not in yi or goal[0] not in xi or goal[1] not in yi:
        return None
    s = (xi[start[0]], yi[start[1]])
    g = (xi[goal[0]], yi[goal[1]])
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    counter = itertools.count()
    open_: list[tuple[float, int, tuple[int, int], tuple[int, int]]] = []
    best: dict[tuple[tuple[int, int], tuple[int, int]], float] = {(s, sdir): 0.0}
    prev: dict[tuple[tuple[int, int], tuple[int, int]], tuple[tuple[int, int], tuple[int, int]] | None] = {
        (s, sdir): None
    }
    heapq.heappush(open_, (0.0, next(counter), s, sdir))
    final_dir = gdir
    while open_:
        _, _, cur, d = heapq.heappop(open_)
        cost = best[(cur, d)]
        if cur == g and d == final_dir:
            # Arrive moving in the goal direction (into the target port stub).
            path = []
            key: tuple[tuple[int, int], tuple[int, int]] | None = (cur, d)
            while key is not None:
                path.append((grid.xs[key[0][0]], grid.ys[key[0][1]]))
                key = prev[key]
            path.reverse()
            return path
        for nd in dirs:
            if nd == (-d[0], -d[1]):
                continue
            nx, ny = cur[0] + nd[0], cur[1] + nd[1]
            if not (0 <= nx < len(grid.xs) and 0 <= ny < len(grid.ys)):
                continue
            x1, y1 = grid.xs[cur[0]], grid.ys[cur[1]]
            x2, y2 = grid.xs[nx], grid.ys[ny]
            if any(_seg_hits_box(x1, y1, x2, y2, b) for b in obstacles):
                continue
            if any(_overlaps(r, x1, y1, x2, y2) for r in routed):
                continue
            step = abs(x2 - x1) + abs(y2 - y1)
            # Bends cost less near the goal, so jogs happen late and leave one long labellable run.
            late = 0.05 * (abs(grid.xs[g[0]] - x1) + abs(grid.ys[g[1]] - y1))
            c = cost + step + (BEND + late if nd != d else 0.0)
            c += CROSS * sum(1 for r in routed if _crosses(r, x1, y1, x2, y2))
            key2 = ((nx, ny), nd)
            if c < best.get(key2, float("inf")):
                best[key2] = c
                prev[key2] = (cur, d)
                h = abs(grid.xs[g[0]] - x2) + abs(grid.ys[g[1]] - y2)
                heapq.heappush(open_, (c + h, next(counter), (nx, ny), nd))
    return None


def _simplify(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for p in points:
        if out and p == out[-1]:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a[0] == b[0] == p[0]) or (a[1] == b[1] == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def path_length(path: list[Point]) -> float:
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in itertools.pairwise(path))


def _route_bus(edges: list[PEdge], nodes: dict[str, PNode], direction: str) -> None:
    """Tree connectors: parent drop -> shared bus -> child drops. Siblings share trunk and bus."""
    lr = direction in ("LR", "RL")
    by_parent: dict[str, list[PEdge]] = {}
    for pe in edges:
        by_parent.setdefault(pe.edge.src, []).append(pe)
    for pid, group in by_parent.items():
        pb = nodes[pid].box
        kids = [nodes[pe.edge.dst].box for pe in group]
        if lr:
            near = min(k.x for k in kids)
            bus = round((pb.right + near) / 2 / 4) * 4
        else:
            near = min(k.y for k in kids)
            bus = round((pb.bottom + near) / 2 / 4) * 4
        for pe in group:
            cb = nodes[pe.edge.dst].box
            pe.bus = True
            if lr:
                pe.src_port = Port("right", pb.right, round(pb.cy), 1.0, 0.5)
                pe.dst_port = Port("left", cb.x, round(cb.cy), 0.0, 0.5)
                pts: list[Point] = [
                    (pb.right, round(pb.cy)),
                    (bus, round(pb.cy)),
                    (bus, round(cb.cy)),
                    (cb.x, round(cb.cy)),
                ]
            else:
                pe.src_port = Port("bottom", round(pb.cx), pb.bottom, 0.5, 1.0)
                pe.dst_port = Port("top", round(cb.cx), cb.y, 0.5, 0.0)
                pts = [
                    (round(pb.cx), pb.bottom),
                    (round(pb.cx), bus),
                    (round(cb.cx), bus),
                    (round(cb.cx), cb.y),
                ]
            pe.path = _simplify(pts)


def _route_loops(loops: list[PEdge], nodes: dict[str, PNode]) -> None:
    """Self-transitions (state machines): a small loop above the box."""
    for pe in loops:
        b = nodes[pe.edge.src].box
        x1, x2 = round(b.x + b.w * 0.3), round(b.x + b.w * 0.7)
        top = b.y - 24
        pe.src_port = Port("top", x1, b.y, 0.3, 0.0)
        pe.dst_port = Port("top", x2, b.y, 0.7, 0.0)
        pe.path = [(x1, b.y), (x1, top), (x2, top), (x2, b.y)]


def route(
    edges: list[PEdge],
    nodes: dict[str, PNode],
    frame: Box,
    direction: str,
    ramp: dict[str, int],
    mode: str = "orthogonal",
) -> None:
    loops = [pe for pe in edges if pe.edge.src == pe.edge.dst]
    _route_loops(loops, nodes)
    if mode == "bus":
        normal = [pe for pe in edges if pe.edge.src != pe.edge.dst]
        _route_bus(normal, nodes, direction)
        _labels_only(edges, nodes, ramp)
        return
    edges_all = edges
    edges = [pe for pe in edges if pe.edge.src != pe.edge.dst]
    _assign_ports(edges, nodes, direction)
    order = sorted(
        edges,
        key=lambda pe: (
            KIND_RANK.get(pe.edge.kind, 9),
            -(
                abs(nodes[pe.edge.src].box.cx - nodes[pe.edge.dst].box.cx)
                + abs(nodes[pe.edge.src].box.cy - nodes[pe.edge.dst].box.cy)
            ),
            pe.edge.index,
        ),
    )
    findings: list[Finding] = []
    boxes = [pn.box for pn in nodes.values()]
    routed: list[Seg] = []
    # Rip-up and reroute: when an edge cannot be routed without touching earlier routes,
    # move it to the front and start again (bounded by the number of edges).
    for _attempt in range(len(order) + 1):
        routed = []
        failed: PEdge | None = None
        for pe in order:
            path = _route_one(pe, nodes, boxes, frame, routed)
            if path is None:
                failed = pe
                break
            pe.path = path
            routed += [Seg(a[0], a[1], b[0], b[1], pe.edge.id) for a, b in itertools.pairwise(path)]
        if failed is None:
            break
        if order[0] is failed:
            break
        order.remove(failed)
        order.insert(0, failed)
    else:
        failed = None
    if failed is not None:
        # Last resort: route the remaining edges ignoring overlaps; lint reports what is left.
        done = {s.edge for s in routed}
        for pe in order:
            if pe.edge.id in done:
                continue
            path = _route_one(pe, nodes, boxes, frame, routed) or _route_one(pe, nodes, boxes, frame, [])
            if path is None:
                findings.append(
                    Finding(
                        "ROUTE-001",
                        f"no orthogonal route for edge {pe.edge.id} ({pe.edge.src} → {pe.edge.dst})",
                        pointer=f"/edges/{pe.edge.index}",
                        fix="add fromSide/toSide hints, change place.rank/order, or mark it transit",
                    )
                )
                continue
            pe.path = path
            routed += [Seg(a[0], a[1], b[0], b[1], pe.edge.id) for a, b in itertools.pairwise(path)]
    if findings:
        raise DDError(findings)
    _labels_only(edges_all, nodes, ramp)


def _labels_only(edges: list[PEdge], nodes: dict[str, PNode], ramp: dict[str, int]) -> None:
    findings: list[Finding] = []
    routed = [Seg(a[0], a[1], b[0], b[1], pe.edge.id) for pe in edges for a, b in itertools.pairwise(pe.path)]
    labels: list[Box] = []
    for pe in edges:
        if pe.edge.label:
            others = [s for s in routed if s.edge != pe.edge.id]
            _place_label(pe, nodes, labels, ramp, findings, others)
    if findings:
        raise DDError(findings)


def _route_one(
    pe: PEdge, nodes: dict[str, PNode], boxes: list[Box], frame: Box, routed: list[Seg]
) -> list[Point] | None:
    sp, dp = pe.src_port, pe.dst_port
    assert sp is not None and dp is not None
    sn, dn = NORMAL[sp.side], NORMAL[dp.side]
    s_stub = (sp.x + sn[0] * STUB, sp.y + sn[1] * STUB)
    d_stub = (dp.x + dn[0] * STUB, dp.y + dn[1] * STUB)
    obstacles = [b.inflate(CLEAR) for b in boxes]
    straight = (sp.x == dp.x or sp.y == dp.y) and _straight_ok(sp, dp, sn, dn, obstacles, nodes, pe)
    if straight and not any(_overlaps(r, sp.x, sp.y, dp.x, dp.y) for r in routed):
        return [(sp.x, sp.y), (dp.x, dp.y)]
    grid = _coords(boxes, [s_stub[0], d_stub[0]], [s_stub[1], d_stub[1]], frame)
    src_box, dst_box = nodes[pe.edge.src].box, nodes[pe.edge.dst].box
    obs = [o for o, b in zip(obstacles, boxes, strict=True) if not (b is src_box or b is dst_box)]
    obs += [src_box.inflate(2), dst_box.inflate(2)]
    # The fixed port-to-stub segments must not run along an existing route either.
    for p, q in (((sp.x, sp.y), s_stub), (d_stub, (dp.x, dp.y))):
        if any(_overlaps(r, p[0], p[1], q[0], q[1]) for r in routed):
            return None
    mid = _astar(s_stub, sn, d_stub, (-dn[0], -dn[1]), grid, obs, routed)
    if mid is None:
        return None
    return _simplify([(sp.x, sp.y), *mid, (dp.x, dp.y)])


def _straight_ok(
    sp: Port,
    dp: Port,
    sn: tuple[int, int],
    dn: tuple[int, int],
    obstacles: list[Box],
    nodes: dict[str, PNode],
    pe: PEdge,
) -> bool:
    # Facing ports on a shared axis: a straight line works if nothing is in between.
    if sn[0] * -1 != dn[0] or sn[1] * -1 != dn[1]:
        return False
    if sn[0] and (dp.x - sp.x) * sn[0] <= 0:
        return False
    if sn[1] and (dp.y - sp.y) * sn[1] <= 0:
        return False
    ends = (nodes[pe.edge.src].box, nodes[pe.edge.dst].box)
    for pn in nodes.values():
        if pn.box in ends:
            continue
        if _seg_hits_box(sp.x, sp.y, dp.x, dp.y, pn.box.inflate(CLEAR)):
            return False
    return True


def _place_label(
    pe: PEdge,
    nodes: dict[str, PNode],
    placed: list[Box],
    ramp: dict[str, int],
    findings: list[Finding],
    others: list[Seg],
) -> None:
    text = pe.edge.label
    lw = round(width(text, ramp["arrow"], "mono", 0.06) + 8)
    lh = max(LABEL_H, ramp["arrow"] + 4)
    total = path_length(pe.path)
    segs = list(itertools.pairwise(pe.path))
    cands: list[tuple[float, int]] = []
    for i, (a, b) in enumerate(segs):
        seg_len = abs(b[0] - a[0]) + abs(b[1] - a[1])
        horizontal = a[1] == b[1]
        need = lw + 8 if horizontal else lh + 8
        if seg_len >= need:
            cands.append((-(seg_len + (1000 if horizontal else 0)), i))
    cands.sort()
    node_boxes = [pn.box for pn in nodes.values()]
    for _, i in cands:
        a, b = segs[i]
        horizontal = a[1] == b[1]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        options = (
            [(0.0, -(LABEL_GAP + lh / 2)), (0.0, LABEL_GAP + lh / 2)]
            if horizontal
            else [(LABEL_GAP + lw / 2, 0.0), (-(LABEL_GAP + lw / 2), 0.0)]
        )
        for ox, oy in options:
            box = Box(mx + ox - lw / 2, my + oy - lh / 2, lw, lh)
            if any(box.intersects(nb.inflate(2)) for nb in node_boxes):
                continue
            if any(box.intersects(lb) for lb in placed):
                continue
            if any(_seg_hits_box(s.x1, s.y1, s.x2, s.y2, box.inflate(2)) for s in others):
                continue
            own = [s for j, s in enumerate(segs) if j != i]
            if any(_seg_hits_box(p[0], p[1], q[0], q[1], box.inflate(5)) for p, q in own):
                continue
            before = sum(abs(q[0] - p[0]) + abs(q[1] - p[1]) for p, q in segs[:i])
            d = before + abs(mx - a[0]) + abs(my - a[1])
            pe.label_param = round(2 * d / total - 1, 4) if total else 0.0
            pe.label_offset = (ox, oy)
            pe.label_box = box
            placed.append(box)
            return
    findings.append(
        Finding(
            "ROUTE-002",
            f"no room for label {text!r} on edge {pe.edge.id}",
            pointer=f"/edges/{pe.edge.index}/label",
            fix="shorten the label, drop it if the layout implies it, or use a larger size preset",
        )
    )
