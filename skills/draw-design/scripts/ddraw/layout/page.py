"""Page composition: frame, header (eyebrow, title, subtitle), content area, legend strip."""

from __future__ import annotations

from ddraw import registry
from ddraw.ir import Box, LegendItem, Page, TextItem
from ddraw.text.measure import ceil4, width

LEGEND_ORDER_NODES = ("focal", "backend", "store", "external", "input", "optional", "security")
LEGEND_ORDER_EDGES = ("accent", "default", "link", "async", "return")
NODE_LABELS = {
    "focal": "FOCAL",
    "backend": "SERVICE",
    "store": "DATA STORE",
    "external": "EXTERNAL",
    "input": "CLIENT / INPUT",
    "optional": "OPTIONAL",
    "security": "SECURITY BOUNDARY",
}
EDGE_LABELS = {
    "accent": "PRIMARY PATH",
    "default": "CALL",
    "link": "HTTP / API",
    "async": "ASYNC",
    "return": "RETURN",
}


def header(page: Page) -> float:
    """Add header text items; return the y where content may start."""
    spec, ramp, safe = page.spec, page.ramp, page.preset["safe"]
    x = page.frame.x + safe
    y = page.frame.y + safe
    eyebrow = (spec.eyebrow or page.spec.type.replace("-", " ")).upper()
    page.texts.append(
        TextItem(
            "title-eyebrow", "eyebrow", eyebrow, Box(x, y, ceil4(width(eyebrow, 8, "mono", 0.18) + 8), 12)
        )
    )
    y += 16
    th = ceil4(ramp["title"] * 1.3)
    page.texts.append(
        TextItem(
            "title", "title", spec.title, Box(x, y, ceil4(width(spec.title, ramp["title"], "serif") + 16), th)
        )
    )
    y += th
    if spec.subtitle:
        page.texts.append(
            TextItem(
                "subtitle",
                "subtitle",
                spec.subtitle,
                Box(x, y + 4, ceil4(width(spec.subtitle, 12, "sans") + 8), 16),
            )
        )
        y += 20
    return float(ceil4(y + 24))


def legend_items(page: Page) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    treatments = {pn.treatment for pn in page.nodes.values()}
    kinds = {pe.edge.kind for pe in page.edges}
    node_keys = [t for t in LEGEND_ORDER_NODES if t in treatments]
    edge_keys = [k for k in LEGEND_ORDER_EDGES if k in kinds]
    if len(node_keys) <= 1 and len(edge_keys) <= 1:
        return [], []
    if len(node_keys) <= 1:
        node_keys = [k for k in node_keys if k != "backend"]
    if len(edge_keys) <= 1:
        edge_keys = [k for k in edge_keys if k != "default"]
    info = registry.types().get(page.spec.type)
    backend_label = info.legend_backend if info else NODE_LABELS["backend"]
    nodes = [(k, backend_label if k == "backend" else NODE_LABELS[k]) for k in node_keys]
    edges = [(k, EDGE_LABELS[k]) for k in edge_keys]
    return nodes, edges


def legend_rows(page: Page, frame_w: float) -> int:
    nodes, edges = legend_items(page)
    if not nodes and not edges:
        return 0
    safe = page.preset["safe"]
    start_x = safe + 72
    x1 = frame_w - safe
    x, rows = start_x, 1
    for _kind, entries in (("node", nodes), ("edge", edges)):
        for _key, label in entries:
            tw = ceil4(width(label, 8, "mono", 0.08) + 4)
            if x + 28 + tw > x1 and x > start_x:
                x = start_x
                rows += 1
            x += 28 + tw + 20
    return rows


def legend_natural_width(page: Page) -> int:
    nodes, edges = legend_items(page)
    total = 72
    for entries in (nodes, edges):
        for _key, label in entries:
            total += 28 + ceil4(width(label, 8, "mono", 0.08) + 4) + 20
    return total - 20 if (nodes or edges) else 0


def strip_height(rows: int) -> int:
    return 24 + 20 * rows if rows else 0


def legend(page: Page, strip_top: float) -> None:
    nodes, edges = legend_items(page)
    if not nodes and not edges:
        return
    safe = page.preset["safe"]
    x0 = page.frame.x + safe
    x1 = page.frame.right - safe
    page.legend_rule = Box(x0, strip_top, x1 - x0, 0)
    row_y = strip_top + 20
    page.texts.append(TextItem("legend-title", "legend-title", "LEGEND", Box(x0, row_y - 4, 56, 16)))
    start_x = x0 + 72
    x = start_x
    for kind, entries in (("node", nodes), ("edge", edges)):
        for key, label in entries:
            tw = ceil4(width(label, 8, "mono", 0.08) + 4)
            if x + 28 + tw > x1 and x > start_x:
                x = start_x
                row_y += 20
            sw = Box(x, row_y, 20, 8) if kind == "node" else Box(x, row_y + 4, 20, 0)
            page.legend.append(
                LegendItem(f"legend-{kind}-{key}", kind, key, label, sw, Box(x + 28, row_y - 4, tw, 16))
            )
            x += 28 + tw + 20
