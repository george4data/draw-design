"""Deterministic draw.io (mxGraph) XML writer (PRD §10.2, Appendix A)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from ddraw import __version__
from ddraw.emit import styles
from ddraw.ir import Box, ExtraCell, Page, PEdge, PNode, Point
from ddraw.theme.model import Theme


def attr(v: str) -> str:
    return (
        v.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#xa;")
    )


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "diagram"


def n(v: float) -> str:
    return styles.fmt(float(v))


class Writer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def cell(
        self,
        cid: str,
        *,
        value: str = "",
        style: str = "",
        parent: str = "1",
        vertex: bool = False,
        edge: bool = False,
        source: str = "",
        target: str = "",
        geometry: str = "",
        user: dict[str, str] | None = None,
        connectable: bool | None = None,
        visible: bool = True,
    ) -> None:
        cell_attrs = []
        if not user:
            cell_attrs.append(f'id="{attr(cid)}"')
            if value or vertex:
                cell_attrs.append(f'value="{attr(value)}"')
        cell_attrs.append(f'style="{attr(style)}"')
        if vertex:
            cell_attrs.append('vertex="1"')
        if edge:
            cell_attrs.append('edge="1"')
        if connectable is False:
            cell_attrs.append('connectable="0"')
        if not visible:
            cell_attrs.append('visible="0"')
        cell_attrs.append(f'parent="{attr(parent)}"')
        if source:
            cell_attrs.append(f'source="{attr(source)}"')
        if target:
            cell_attrs.append(f'target="{attr(target)}"')
        cell_xml = f"<mxCell {' '.join(cell_attrs)}>{geometry}</mxCell>"
        if user:
            ua = (
                [f'label="{attr(value)}"']
                + [f'{k}="{attr(v)}"' for k, v in user.items()]
                + [f'id="{attr(cid)}"']
            )
            self.lines.append(f"        <UserObject {' '.join(ua)}>{cell_xml}</UserObject>")
        else:
            self.lines.append(f"        {cell_xml}")


def geom(b: Box, ox: float = 0.0, oy: float = 0.0) -> str:
    return (
        f'<mxGeometry x="{n(b.x - ox)}" y="{n(b.y - oy)}" width="{n(b.w)}" height="{n(b.h)}" as="geometry"/>'
    )


def edge_geom(
    points: list[Point], ox: float, oy: float, label_param: float, offset: Point, has_label: bool
) -> str:
    parts = []
    xattr = f' x="{n(label_param)}"' if has_label else ""
    parts.append(f'<mxGeometry{xattr} relative="1" as="geometry">')
    if points:
        pts = "".join(f'<mxPoint x="{n(p[0] - ox)}" y="{n(p[1] - oy)}"/>' for p in points)
        parts.append(f'<Array as="points">{pts}</Array>')
    if has_label:
        parts.append(f'<mxPoint x="{n(offset[0])}" y="{n(offset[1])}" as="offset"/>')
    parts.append("</mxGeometry>")
    return "".join(parts)


def node_label(pn: PNode, theme: Theme, ramp: dict[str, int]) -> str:
    if pn.shape in ("dot", "ring"):
        return ""
    name = (
        f'<div style="font-family:{theme.font("sans")};font-weight:600;font-size:{ramp["node"]}px;'
        f'line-height:1.25">{esc(pn.node.label)}</div>'
    )
    if not pn.node.sublabel:
        return name
    sub = (
        f'<div style="font-family:{theme.font("mono")};font-weight:400;font-size:{ramp["sublabel"]}px;'
        f'line-height:1.3;margin-top:2px;opacity:0.78">{esc(pn.node.sublabel)}</div>'
    )
    return name + sub


def tracked(text: str, em: float) -> str:
    return f'<span style="letter-spacing:{em}em">{esc(text)}</span>'


def write(page: Page, theme: Theme) -> str:
    spec, ramp = page.spec, page.ramp
    w = Writer()
    w.lines.append('        <mxCell id="0"/>')
    w.lines.append('        <mxCell id="frame-layer" value="Frame" style="locked=1;" parent="0"/>')
    w.lines.append('        <mxCell id="1" value="Diagram" parent="0"/>')
    w.cell("frame", style=styles.frame_style(), parent="frame-layer", vertex=True, geometry=geom(page.frame))

    meta = {
        "dd-role": "title",
        "dd-type": spec.type,
        "dd-size": spec.size,
        "dd-detail": spec.detail,
        "dd-direction": page.direction,
        "dd-description": spec.description,
        "dd-theme": theme.slug,
        "dd-version": __version__,
    }
    for t in page.texts:
        if t.role == "title":
            w.cell(
                "dd-title",
                value=esc(t.text),
                style=styles.text_style(theme, "title", ramp["title"]),
                vertex=True,
                geometry=geom(t.box),
                user=meta,
            )
        elif t.role == "eyebrow":
            w.cell(
                "dd-eyebrow",
                value=tracked(t.text, 0.18),
                style=styles.text_style(theme, "eyebrow", 8),
                vertex=True,
                geometry=geom(t.box),
                user={"dd-role": "eyebrow"},
            )
        elif t.role == "subtitle":
            w.cell(
                "dd-subtitle",
                value=esc(t.text),
                style=styles.text_style(theme, "subtitle", 12),
                vertex=True,
                geometry=geom(t.box),
                user={"dd-role": "subtitle"},
            )

    def parent_of_zone(zid: str) -> tuple[str, Box | None]:
        parent = page.zones[zid].zone.parent
        return (f"dd-{parent}", page.zones[parent].box) if parent else ("1", None)

    for zid, pz in sorted(page.zones.items(), key=lambda kv: (kv[1].depth, kv[1].zone.index)):
        pid, pbox = parent_of_zone(zid)
        ox, oy = (pbox.x, pbox.y) if pbox else (0.0, 0.0)
        w.cell(
            f"dd-{zid}",
            value=tracked(pz.zone.label.upper(), 0.14),
            style=styles.zone_style(theme, pz.zone.role, pz.depth),
            parent=pid,
            vertex=True,
            geometry=geom(pz.box, ox, oy),
            user={"dd-role": "zone", "dd-id": zid, "dd-zone-role": pz.zone.role},
        )

    def node_parent(pn: PNode) -> tuple[str, float, float]:
        if pn.node.zone and pn.node.zone in page.zones:
            zb = page.zones[pn.node.zone].box
            return f"dd-{pn.node.zone}", zb.x, zb.y
        return "1", 0.0, 0.0

    def zone_chain(zid: str) -> list[str]:
        chain = []
        while zid:
            chain.append(zid)
            zid = page.zones[zid].zone.parent if zid in page.zones else ""
        return chain

    for x in page.extras:
        if x.role in ("fragment", "guard", "else"):
            _write_extra(w, x, page, theme)

    # Edges are normally written before nodes so lines sit behind boxes.
    if page.edges_first:
        for pe in sorted(page.edges, key=lambda e: e.edge.index):
            _write_edge(w, pe, page, theme, zone_chain)

    for pn in sorted(page.nodes.values(), key=lambda p: p.node.index):
        pid, ox, oy = node_parent(pn)
        user = {"dd-role": pn.node.role, "dd-id": pn.id, "dd-treatment": pn.treatment}
        if pn.shape in ("dot", "ring"):
            user["tooltip"] = pn.node.label
        if pn.node.focal:
            user["dd-focal"] = "1"
        for k, v in sorted(pn.node.meta.items()):
            if k == "url" and v.startswith("https://"):
                user["link"] = v
            else:
                user[f"dd-meta-{k}"] = v
        w.cell(
            f"dd-{pn.id}",
            value=node_label(pn, theme, ramp),
            style=styles.node_style(
                theme,
                pn.treatment,
                pn.shape,
                bool(pn.node.tag),
                spec.sketch,
                pn.box.h,
                page.ramp["minNodeHeight"],
            ),
            parent=pid,
            vertex=True,
            geometry=geom(pn.box, ox, oy),
            user=user,
        )
        if pn.node.tag:
            tw = max(28, round(len(pn.node.tag) * 7 * 0.62 + 10))
            tw = (tw + 3) // 4 * 4
            tb = Box(8, 8, tw, 12)
            w.cell(
                f"dd-{pn.id}-tag",
                value=tracked(pn.node.tag, 0.08),
                style=styles.tag_style(theme, pn.treatment),
                parent=f"dd-{pn.id}",
                vertex=True,
                geometry=geom(tb),
                connectable=False,
                user={"dd-role": "tag"},
            )

    for x in page.extras:
        if x.role == "activation":
            _write_extra(w, x, page, theme)
    if not page.edges_first:
        for pe in sorted(page.edges, key=lambda e: e.edge.index):
            _write_edge(w, pe, page, theme, zone_chain)

    for t, target in page.callouts:
        w.cell(
            f"dd-{t.id}",
            value=esc(t.text),
            style=styles.text_style(theme, "callout", 14, t.align),
            vertex=True,
            geometry=geom(t.box),
            user={"dd-role": "callout", "dd-target": target},
        )

    if page.legend_rule:
        r = page.legend_rule
        w.cell(
            "dd-legend-rule",
            style=styles.rule_style(theme),
            vertex=True,
            geometry=geom(Box(r.x, r.y - 4, r.w, 8)),
            user={"dd-role": "legend"},
        )
    for t in page.texts:
        if t.role == "legend-title":
            w.cell(
                "dd-legend-title",
                value=tracked(t.text, 0.14),
                style=styles.text_style(theme, "legend-title", 8),
                vertex=True,
                geometry=geom(t.box),
                user={"dd-role": "legend"},
            )
    for item in page.legend:
        w.cell(
            f"dd-{item.id}",
            style=styles.legend_swatch(theme, item.kind, item.key),
            vertex=True,
            geometry=geom(
                item.swatch if item.kind == "node" else Box(item.swatch.x, item.swatch.y - 4, 20, 8)
            ),
            user={"dd-role": "legend", "dd-legend-key": item.key},
        )
        w.cell(
            f"dd-{item.id}-text",
            value=tracked(item.label, 0.08),
            style=styles.text_style(theme, "legend", 8),
            vertex=True,
            geometry=geom(item.text),
            user={"dd-role": "legend"},
        )

    if spec.ledger:
        w.lines.append(
            '        <mxCell id="notes-layer" value="Notes" style="locked=1;" parent="0" visible="0"/>'
        )
        lines = [spec.ledger.get("summary", "")]
        for key in ("merged", "collapsed", "dropped", "kept"):
            for item in spec.ledger.get(key, []):
                lines.append(f"{key.capitalize()}: {item}")
        text = "<br>".join(esc(x) for x in lines if x)
        w.cell(
            "dd-ledger",
            value=text,
            style=styles.text_style(theme, "legend", 9),
            parent="notes-layer",
            vertex=True,
            geometry=geom(Box(page.frame.x + 40, page.frame.y + 40, 400, 16 * len(lines))),
            user={"dd-role": "ledger"},
        )

    page_id = f"p-{slug(spec.title)}"
    model_attrs = (
        'grid="1" gridSize="4" guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
        'page="0" pageScale="1" '
        f'pageWidth="{n(page.frame.w)}" pageHeight="{n(page.frame.h)}" math="0" shadow="0" '
        f'background="{attr(theme.c("paper"))}" adaptiveColors="none"'
    )
    body = "\n".join(w.lines)
    return (
        f'<mxfile host="draw-design" agent="ddraw/{__version__}" compressed="false">\n'
        f'  <diagram id="{page_id}" name="{attr(spec.title)}">\n'
        f"    <mxGraphModel {model_attrs}>\n"
        f"      <root>\n{body}\n      </root>\n"
        f"    </mxGraphModel>\n"
        f"  </diagram>\n"
        f"</mxfile>\n"
    )


def _write_edge(
    w: Writer, pe: PEdge, page: Page, theme: Theme, zone_chain: Callable[[str], list[str]]
) -> None:
    e = pe.edge
    chain = zone_chain
    src_zone = page.nodes[e.src].node.zone
    dst_zone = page.nodes[e.dst].node.zone
    src_chain = chain(src_zone) if src_zone else []
    dst_chain = chain(dst_zone) if dst_zone else []
    common = next((z for z in src_chain if z in dst_chain), "")
    pid, ox, oy = ("1", 0.0, 0.0)
    if common:
        zb = page.zones[common].box
        pid, ox, oy = f"dd-{common}", zb.x, zb.y
    sp, dp = pe.src_port, pe.dst_port
    assert sp is not None and dp is not None
    points = pe.path[1:-1]
    style = styles.edge_style(
        theme,
        e.kind,
        (sp.fx, sp.fy, dp.fx, dp.fy),
        e.bidirectional,
        e.transit,
        page.ramp["arrow"],
        straight=page.prerouted and len(pe.path) == 2,
    )
    value = tracked(e.label, 0.06) if e.label else ""
    w.cell(
        f"dd-{e.id}",
        value=value,
        style=style,
        parent=pid,
        edge=True,
        source=f"dd-{e.src}",
        target=f"dd-{e.dst}",
        geometry=edge_geom(points, ox, oy, pe.label_param, pe.label_offset, bool(e.label)),
        user={
            "dd-role": "edge",
            "dd-id": e.id,
            "dd-kind": e.kind,
            **({"dd-transit": "1"} if e.transit else {}),
            **({"dd-bus": "1"} if pe.bus else {}),
        },
    )


def _write_extra(w: Writer, x: ExtraCell, page: Page, theme: Theme) -> None:
    parent = f"dd-{x.parent}" if x.parent else "1"
    if x.role == "fragment":
        value = tracked(x.label, 0.08)
    elif x.role == "guard":
        value = esc(x.label)
    else:
        value = ""
    w.cell(
        f"dd-{x.id}",
        value=value,
        style=styles.extra_style(theme, x.role),
        parent=parent,
        vertex=True,
        geometry=geom(x.box),
        connectable=False,
        user={"dd-role": x.role},
    )
