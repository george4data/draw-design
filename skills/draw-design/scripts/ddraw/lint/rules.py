"""Lint rules (PRD §16.2). Each rule is a pure function of (page, context) -> findings."""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from ddraw import registry
from ddraw.errors import Finding
from ddraw.ir import Box, Point
from ddraw.layout.page import LEGEND_ORDER_EDGES, LEGEND_ORDER_NODES
from ddraw.lint.model import Cell, DrawPage
from ddraw.text.measure import width
from ddraw.theme.model import Theme

NON_NODE_ROLES = {
    "title",
    "eyebrow",
    "subtitle",
    "zone",
    "tag",
    "legend",
    "callout",
    "ledger",
    "edge",
    "",
    "activation",
    "fragment",
    "guard",
    "else",
}


def obstacle(c: Cell) -> Box:
    """The part of a node that connectors and labels must avoid (a lifeline's header only)."""
    assert c.abs_box is not None
    if c.style.get("shape") == "umlLifeline":
        b = c.abs_box
        return Box(b.x, b.y, b.w, float(c.style.get("size", "40")))
    return c.abs_box


SAFE_LINK = re.compile(r"^(https://|mailto:|data:page/id,)")
COLOR_KEYS = ("fillColor", "strokeColor", "fontColor", "labelBackgroundColor")
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
FONT_CSS = re.compile(r"font-family:\s*([^;\"]+)")


@dataclass
class Context:
    theme: Theme | None
    compiled: bool  # file was produced by ddraw (has dd-* metadata)
    dtype: str
    detail: str
    safe: int


Rule = Callable[[DrawPage, Context], list[Finding]]


def sev(ctx: Context, severity: str = "error") -> str:
    return severity if ctx.compiled else "info"


def _is_node(page: DrawPage, c: Cell) -> bool:
    if not c.vertex or c.abs_box is None or c.id == "frame":
        return False
    if c.role:
        return c.role not in NON_NODE_ROLES
    # Foreign files: anything box-like that is not text, a container, a line or an edge label.
    parent = page.cells.get(c.parent)
    if parent is not None and parent.edge:
        return False
    return not (
        c.base in ("text", "edgeLabel", "line", "swimlane", "group")
        or c.style.get("container") == "1"
        or c.style.get("shape") in ("line", "swimlane", "table")
    )


def _nodes(page: DrawPage) -> list[Cell]:
    return [c for c in page.cells.values() if _is_node(page, c)]


def _edges(page: DrawPage) -> list[Cell]:
    return [c for c in page.cells.values() if c.edge]


# ---------------------------------------------------------------- structure


def s001(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    root = page.cells.get("0")
    if root is None or root.parent:
        out.append(Finding("LR-S001", 'missing root cell id="0"'))
    if not any(c.parent == "0" for c in page.cells.values() if c.id != "0"):
        out.append(Finding("LR-S001", 'no layer cell (a cell whose parent is "0")'))
    return out


def s002(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    if "__dupes__" in page.cells:
        out.append(Finding("LR-S002", f"duplicate cell ids: {page.cells['__dupes__'].value}"))
    for c in page.cells.values():
        if c.id in ("0", "__dupes__"):
            continue
        if not c.id:
            out.append(Finding("LR-S002", "cell without id"))
        if c.parent not in page.cells:
            out.append(Finding("LR-S002", f"parent {c.parent!r} does not exist", cell=c.id))
        if c.vertex and c.edge:
            out.append(Finding("LR-S002", "cell is both vertex and edge", cell=c.id))
        seen = {c.id}
        p = c.parent
        while p in page.cells and p != "0":
            if p in seen:
                out.append(Finding("LR-S002", "parent cycle", cell=c.id))
                break
            seen.add(p)
            p = page.cells[p].parent
    return out


def s003(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in _edges(page):
        for end, key in ((c.source, "source"), (c.target, "target")):
            if not end:
                out.append(Finding("LR-S003", f"edge has no {key}", cell=c.id, severity=sev(ctx, "warn")))
            elif end not in page.cells:
                out.append(Finding("LR-S003", f"edge {key} {end!r} does not exist", cell=c.id))
    return out


def s004(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in page.cells.values():
        if c.vertex:
            g = c.geom
            if not g or any(math.isnan(g.get(k, 0.0)) or math.isinf(g.get(k, 0.0)) for k in g):
                out.append(Finding("LR-S004", "vertex without finite geometry", cell=c.id))
            elif (g.get("width", 0) <= 0 or g.get("height", 0) <= 0) and c.base != "line":
                out.append(Finding("LR-S004", "vertex has zero size", cell=c.id))
    return out


def s005(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    bad = re.compile(r"<\s*script|\bon[a-z]+\s*=|javascript:|<\s*iframe|<\s*object", re.I)
    for c in page.cells.values():
        for text in (c.value, c.attrs.get("tooltip", "")):
            if text and bad.search(text):
                out.append(
                    Finding("LR-S005", "label contains script, event handler or javascript: URL", cell=c.id)
                )
    return out


def s007(page: DrawPage, ctx: Context) -> list[Finding]:
    if not ctx.compiled:
        return []
    title = page.cells.get("dd-title")
    if title is None or not title.text.strip():
        return [Finding("LR-S007", "diagram has no title cell")]
    if len(title.attrs.get("dd-description", "")) < 10:
        return [
            Finding("LR-S007", "diagram has no description (needed for accessible export)", cell="dd-title")
        ]
    return []


# ---------------------------------------------------------------- grid & bounds


def g001(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in page.cells.values():
        if not c.vertex or c.abs_box is None or c.id == "frame":
            continue
        b = c.abs_box
        bad = [
            k
            for k, v in (("x", b.x), ("y", b.y), ("width", b.w), ("height", b.h))
            if round(v) % 4 or v != round(v)
        ]
        if bad:
            out.append(
                Finding(
                    "LR-G001",
                    f"off the 4px grid ({', '.join(bad)})",
                    cell=c.id,
                    severity=sev(ctx),
                    fix="snap origin and size to multiples of 4",
                )
            )
    return out


def _frame(page: DrawPage) -> Box:
    f = page.cells.get("frame")
    if f is not None and f.abs_box is not None:
        return f.abs_box
    return Box(0, 0, page.width, page.height)


def g003(page: DrawPage, ctx: Context) -> list[Finding]:
    if not ctx.compiled:
        return []
    frame = _frame(page)
    inner = Box(
        frame.x + ctx.safe - 0.5,
        frame.y + ctx.safe - 0.5,
        frame.w - 2 * ctx.safe + 1,
        frame.h - 2 * ctx.safe + 1,
    )
    out = []
    for c in page.cells.values():
        if (
            c.vertex
            and c.abs_box is not None
            and c.id != "frame"
            and c.parent not in ("notes-layer",)
            and c.role != "ledger"
            and not inner.contains(c.abs_box)
        ):
            out.append(
                Finding(
                    "LR-G003",
                    f"outside the {ctx.safe}px safe area",
                    cell=c.id,
                    fix="use a larger size preset or reduce content",
                )
            )
    return out


def g004(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    nodes = _nodes(page)
    for a, b in itertools.combinations(nodes, 2):
        assert a.abs_box is not None and b.abs_box is not None
        if a.parent == b.id or b.parent == a.id:
            continue
        if obstacle(a).intersects(obstacle(b)):
            out.append(Finding("LR-G004", f"overlaps {b.id}", cell=a.id, severity=sev(ctx)))
    return out


# ---------------------------------------------------------------- budget


def budget_rules(page: DrawPage, ctx: Context) -> list[Finding]:
    if not ctx.compiled or ctx.dtype not in registry.types():
        return []
    budget = registry.type_budget(ctx.dtype, ctx.detail)
    nodes = _nodes(page)
    edges = _edges(page)
    out = []
    if len(nodes) > budget["nodes"]:
        out.append(
            Finding(
                "LR-B001",
                f"{len(nodes)} nodes; budget is {budget['nodes']}",
                fix="merge or split into overview + detail",
            )
        )
    if len(edges) > budget["edges"]:
        out.append(Finding("LR-B002", f"{len(edges)} edges; budget is {budget['edges']}"))
    accents = sum(1 for c in nodes if c.attrs.get("dd-focal") == "1") + sum(
        1 for c in edges if c.attrs.get("dd-kind") == "accent"
    )
    if accents > budget["accent"]:
        out.append(Finding("LR-B003", f"{accents} accent elements; at most {budget['accent']}"))
    callouts = sum(1 for c in page.cells.values() if c.role == "callout")
    if callouts > budget["callouts"]:
        out.append(Finding("LR-B004", f"{callouts} callouts; at most {budget['callouts']}"))
    return out


# ---------------------------------------------------------------- connectors


def _segments(c: Cell) -> list[tuple[Point, Point]]:
    return [(a, b) for a, b in itertools.pairwise(c.path) if a != b]


def _exempt(c: Cell) -> bool:
    return c.style.get("curved") == "1" or (c.style.get("edgeStyle") == "none" and c.role == "callout-leader")


def c001(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in _edges(page):
        if _exempt(c):
            continue
        if not c.points and c.style.get("edgeStyle") in (
            "orthogonalEdgeStyle",
            "elbowEdgeStyle",
            "segmentEdgeStyle",
            "entityRelationEdgeStyle",
        ):
            continue  # renderer routes it orthogonally
        for a, b in _segments(c):
            if a[0] != b[0] and a[1] != b[1]:
                out.append(
                    Finding(
                        "LR-C001",
                        f"diagonal segment {a} → {b}",
                        cell=c.id,
                        severity=sev(ctx),
                        fix="route with right-angle bends",
                    )
                )
                break
    return out


def _label_box(c: Cell) -> Box | None:
    if not c.text.strip() or len(c.path) < 2:
        return None
    total = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in itertools.pairwise(c.path))
    if total == 0:
        return None
    t = (c.geom.get("x", 0.0) + 1) / 2 * total if c.relative else total / 2
    acc = 0.0
    px, py = c.path[0]
    for a, b in itertools.pairwise(c.path):
        seg = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if acc + seg >= t:
            r = (t - acc) / seg if seg else 0
            px, py = a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r
            break
        acc += seg
    px += c.offset[0]
    py += c.offset[1]
    size = float(c.style.get("fontSize", "11"))
    w = round(width(c.text.strip(), size, "mono", 0.06) + 8)
    h = max(12.0, size + 4)
    return Box(px - w / 2, py - h / 2, w, h)


def c002(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in _edges(page):
        lb = _label_box(c)
        if lb is None:
            continue
        if c.style.get("labelBackgroundColor", "none") == "none":
            out.append(Finding("LR-C002", "edge label has no background mask", cell=c.id, severity=sev(ctx)))
        gaps = []
        for a, b in _segments(c):
            if a[1] == b[1] and min(a[0], b[0]) <= lb.cx <= max(a[0], b[0]):
                gaps.append(
                    min(abs(lb.y - a[1]), abs(lb.bottom - a[1])) * (-1 if lb.y < a[1] < lb.bottom else 1)
                )
            if a[0] == b[0] and min(a[1], b[1]) <= lb.cy <= max(a[1], b[1]):
                gaps.append(
                    min(abs(lb.x - a[0]), abs(lb.right - a[0])) * (-1 if lb.x < a[0] < lb.right else 1)
                )
        if gaps:
            g = min(gaps, key=abs)
            if g < 6 - 0.5:
                out.append(
                    Finding(
                        "LR-C002",
                        f"label sits {g:.0f}px from its connector (needs 6–10px)",
                        cell=c.id,
                        severity=sev(ctx),
                        fix="offset the label 8px off the stroke",
                    )
                )
    return out


def c003(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    segs = [(c.id, a, b) for c in _edges(page) if not _exempt(c) for a, b in _segments(c)]
    bus_src = {c.id: c.source for c in _edges(page) if c.attrs.get("dd-bus") == "1"}
    reported: set[tuple[str, str]] = set()
    for (ia, a1, a2), (ib, b1, b2) in itertools.combinations(segs, 2):
        if ia == ib or (ia, ib) in reported:
            continue
        if ia in bus_src and ib in bus_src and bus_src[ia] == bus_src[ib]:
            continue  # tree siblings share their parent's trunk and bus by design
        if a1[1] == a2[1] and b1[1] == b2[1] and abs(a1[1] - b1[1]) < 12:
            ov = min(max(a1[0], a2[0]), max(b1[0], b2[0])) - max(min(a1[0], a2[0]), min(b1[0], b2[0]))
        elif a1[0] == a2[0] and b1[0] == b2[0] and abs(a1[0] - b1[0]) < 12:
            ov = min(max(a1[1], a2[1]), max(b1[1], b2[1])) - max(min(a1[1], a2[1]), min(b1[1], b2[1]))
        else:
            continue
        if ov > 1:
            reported.add((ia, ib))
            out.append(
                Finding(
                    "LR-C003",
                    f"runs on top of (or within 12px of) {ib}",
                    cell=ia,
                    severity=sev(ctx),
                    fix="offset parallel routes by at least 12px",
                )
            )
    return out


def c004(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    ports: dict[tuple[str, str], list[float]] = {}
    for c in _edges(page):
        if c.attrs.get("dd-bus") == "1" or c.source == c.target:
            continue
        for cid, prefix in ((c.source, "exit"), (c.target, "entry")):
            cell = page.cells.get(cid)
            if cell is None or cell.abs_box is None or f"{prefix}X" not in c.style:
                continue
            fx, fy = float(c.style[f"{prefix}X"]), float(c.style[f"{prefix}Y"])
            b = cell.abs_box
            if fy in (0.0, 1.0):
                ports.setdefault((cid, "top" if fy == 0 else "bottom"), []).append(b.w * fx)
            elif fx in (0.0, 1.0):
                ports.setdefault((cid, "left" if fx == 0 else "right"), []).append(b.h * fy)
    for (cid, side), offs in ports.items():
        cell = page.cells[cid]
        assert cell.abs_box is not None
        length = cell.abs_box.w if side in ("top", "bottom") else cell.abs_box.h
        need = 8 if length < 80 else 12
        offs.sort()
        for lo, hi in itertools.pairwise(offs):
            if hi - lo < need - 0.5:
                out.append(
                    Finding(
                        "LR-C004",
                        f"two connectors attach {hi - lo:.0f}px apart on the {side} side",
                        cell=cid,
                        severity=sev(ctx),
                        fix="spread attach points at L·k/(N+1)",
                    )
                )
                break
        shape_rounded = cell.base not in ("rhombus", "ellipse")
        if shape_rounded and offs and (offs[0] < 8 - 0.5 or length - offs[-1] < 8 - 0.5):
            out.append(
                Finding(
                    "LR-C004",
                    f"attach point within 8px of a corner on the {side} side",
                    cell=cid,
                    severity=sev(ctx, "warn"),
                )
            )
    return out


def c005(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    nodes = _nodes(page)
    for c in _edges(page):
        if c.attrs.get("dd-transit") == "1" or _exempt(c):
            continue
        for a, b in _segments(c):
            for n in nodes:
                if n.id in (c.source, c.target) or n.abs_box is None:
                    continue
                bx = obstacle(n).inflate(-1)
                if (
                    min(a[0], b[0]) < bx.right
                    and max(a[0], b[0]) > bx.x
                    and min(a[1], b[1]) < bx.bottom
                    and max(a[1], b[1]) > bx.y
                ):
                    out.append(
                        Finding(
                            "LR-C005",
                            f"passes behind {n.id}",
                            cell=c.id,
                            severity=sev(ctx),
                            fix="reroute around the box, or mark the edge transit (dashed)",
                        )
                    )
                    break
    return out


def c006(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    nodes = _nodes(page)
    labels = [(c, _label_box(c)) for c in _edges(page)]
    for c, lb in labels:
        if lb is None:
            continue
        for n in nodes:
            if n.abs_box is not None and lb.intersects(obstacle(n)):
                out.append(
                    Finding(
                        "LR-C006",
                        f"label overlaps node {n.id}",
                        cell=c.id,
                        severity=sev(ctx),
                        fix="move the label to a segment in open canvas",
                    )
                )
                break
    return out


def c007(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    info = registry.types().get(ctx.dtype)
    limit = info.edge_label_max if info else 14
    upper = info.upper_labels if info else True
    for c in _edges(page):
        t = c.text.strip()
        if len(t) > limit:
            out.append(
                Finding(
                    "LR-C007",
                    f"edge label {t!r} is longer than {limit} characters",
                    cell=c.id,
                    severity="warn",
                )
            )
        elif upper and t and t != t.upper():
            out.append(Finding("LR-C007", f"edge label {t!r} is not uppercase", cell=c.id, severity="warn"))
    return out


# ---------------------------------------------------------------- theme & typography


def _colours(value: str) -> list[str]:
    if value.startswith("light-dark("):
        inner = value[len("light-dark(") : -1]
        return [p.strip().lower() for p in inner.split(",")]
    return [value.lower()]


def t001(page: DrawPage, ctx: Context) -> list[Finding]:
    if ctx.theme is None or not ctx.compiled:
        return []
    palette = ctx.theme.palette()
    out = []
    for c in page.cells.values():
        used: list[str] = []
        for k in COLOR_KEYS:
            if k in c.style and c.style[k] not in ("none", "default", "inherit"):
                used += _colours(c.style[k])
        used += [h.lower() for h in HEX.findall(c.value)]
        bad = sorted({u for u in used if u.startswith("#") and u not in palette})
        if bad:
            out.append(
                Finding(
                    "LR-T001",
                    f"colours outside the theme palette: {', '.join(bad)}",
                    cell=c.id,
                    fix="use theme roles only",
                )
            )
    return out


def t002(page: DrawPage, ctx: Context) -> list[Finding]:
    if ctx.theme is None or not ctx.compiled:
        return []
    allowed = {ctx.theme.font(r) for r in ("title", "sans", "mono", "callout")}
    out = []
    for c in page.cells.values():
        fams = [c.style["fontFamily"]] if "fontFamily" in c.style else []
        fams += [m.strip() for m in FONT_CSS.findall(c.value)]
        bad = sorted({f for f in fams if f not in allowed})
        if bad:
            out.append(Finding("LR-T002", f"font families outside the theme: {', '.join(bad)}", cell=c.id))
    return out


def t005(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in page.cells.values():
        bad = [k for k in ("shadow", "glass") if c.style.get(k) == "1"]
        if c.style.get("gradientColor", "none") not in ("none", ""):
            bad.append("gradientColor")
        if bad:
            out.append(
                Finding(
                    "LR-T005",
                    f"decorative effects not allowed: {', '.join(bad)}",
                    cell=c.id,
                    severity=sev(ctx),
                    fix="borders, not shadows or gradients",
                )
            )
    return out


# ---------------------------------------------------------------- legend


def l001(page: DrawPage, ctx: Context) -> list[Finding]:
    if not ctx.compiled:
        return []
    treatments = {c.attrs.get("dd-treatment", "") for c in _nodes(page)} - {""}
    kinds = {c.attrs.get("dd-kind", "") for c in _edges(page)} - {""}
    present = {c.attrs.get("dd-legend-key", "") for c in page.cells.values() if c.attrs.get("dd-legend-key")}
    node_keys = [t for t in LEGEND_ORDER_NODES if t in treatments]
    edge_keys = [k for k in LEGEND_ORDER_EDGES if k in kinds]
    if len(node_keys) <= 1 and len(edge_keys) <= 1:
        return []
    needed = set(node_keys if len(node_keys) > 1 else []) | set(edge_keys if len(edge_keys) > 1 else [])
    out = []
    missing = needed - present
    extra = present - set(node_keys) - set(edge_keys)
    if missing:
        out.append(Finding("LR-L001", f"legend misses: {', '.join(sorted(missing))}"))
    if extra:
        out.append(Finding("LR-L001", f"legend lists unused keys: {', '.join(sorted(extra))}"))
    return out


# ---------------------------------------------------------------- safety


def x001(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in page.cells.values():
        link = c.attrs.get("link", "")
        if link and not SAFE_LINK.match(link):
            sev_ = "warn" if link.startswith("http://") else "error"
            out.append(
                Finding("LR-X001", f"link scheme not allowed: {link[:40]!r}", cell=c.id, severity=sev_)
            )
    return out


def x002(page: DrawPage, ctx: Context) -> list[Finding]:
    out = []
    for c in page.cells.values():
        img = c.style.get("image", "")
        if img and not (
            img.startswith("data:image/svg+xml,")
            or img.startswith("data:image/png,")
            or img.startswith("img/lib/")
        ):
            out.append(
                Finding(
                    "LR-X002",
                    "image must be an embedded data URI or a draw.io built-in path",
                    cell=c.id,
                    severity=sev(ctx),
                )
            )
    return out


RULES: list[Rule] = [
    s001,
    s002,
    s003,
    s004,
    s005,
    s007,
    g001,
    g003,
    g004,
    budget_rules,
    c001,
    c002,
    c003,
    c004,
    c005,
    c006,
    c007,
    t001,
    t002,
    t005,
    l001,
    x001,
    x002,
]
