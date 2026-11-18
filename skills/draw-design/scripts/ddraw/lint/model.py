"""Parse a .drawio file into a lint model with absolute geometry and reconstructed edge paths."""

from __future__ import annotations

import base64
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field

from ddraw.errors import DDError, Finding
from ddraw.ir import Box, Point

MAX_BYTES = 20 * 1024 * 1024
MAX_INFLATED = 50 * 1024 * 1024
MAX_PAGES = 100
MAX_CELLS = 10_000


@dataclass
class Cell:
    id: str
    parent: str
    vertex: bool
    edge: bool
    base: str
    style: dict[str, str]
    value: str
    attrs: dict[str, str]
    geom: dict[str, float]
    relative: bool = False
    points: list[Point] = field(default_factory=list)
    offset: Point = (0.0, 0.0)
    source: str = ""
    target: str = ""
    visible: bool = True
    abs_box: Box | None = None
    path: list[Point] = field(default_factory=list)

    @property
    def role(self) -> str:
        return self.attrs.get("dd-role", "")

    @property
    def text(self) -> str:
        return strip_html(self.value)


@dataclass
class DrawPage:
    id: str
    name: str
    width: float
    height: float
    background: str
    cells: dict[str, Cell]
    order: list[str]


@dataclass
class Doc:
    pages: list[DrawPage]
    compressed: bool
    source: str


_TAG = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    v = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    v = re.sub(r"</div>\s*<div", "</div>\n<div", v)
    v = _TAG.sub("", v)
    return (
        v.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )


def parse_style(style: str) -> tuple[str, dict[str, str]]:
    base = ""
    out: dict[str, str] = {}
    for i, part in enumerate(p for p in style.split(";") if p):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
        elif i == 0:
            base = part
        else:
            out[part] = "1"
    return base, out


def decompress(payload: str) -> str:
    raw = base64.b64decode(payload)
    d = zlib.decompressobj(-15)
    data = d.decompress(raw, MAX_INFLATED)
    if d.unconsumed_tail:
        raise DDError([Finding("LR-S001", "compressed diagram exceeds the size limit")])
    text = data.decode("utf-8")
    return urllib.parse.unquote(text) if text.startswith("%3C") else text


def _reject_unsafe(xml: str) -> None:
    head = xml[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in xml.upper():
        raise DDError([Finding("LR-S001", "XML with DTD or entity declarations is rejected")])


def load(text: str, source: str = "<input>") -> Doc:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise DDError([Finding("LR-S001", "file exceeds 20 MB")])
    _reject_unsafe(text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DDError([Finding("LR-S001", f"not well-formed XML: {exc}")]) from exc
    compressed = False
    models: list[tuple[str, str, ET.Element]] = []
    if root.tag == "mxGraphModel":
        models.append(("page-1", "Page-1", root))
    elif root.tag == "mxfile":
        diagrams = root.findall("diagram")
        if len(diagrams) > MAX_PAGES:
            raise DDError([Finding("LR-S001", f"page limit exceeded (max {MAX_PAGES})")])
        for i, d in enumerate(diagrams):
            m = d.find("mxGraphModel")
            if m is None and (d.text or "").strip():
                compressed = True
                inner = decompress((d.text or "").strip())
                _reject_unsafe(inner)
                m = ET.fromstring(inner)
            if m is None:
                raise DDError([Finding("LR-S001", f"page {i + 1} has no mxGraphModel")])
            models.append((d.get("id", f"page-{i + 1}"), d.get("name", f"Page-{i + 1}"), m))
    else:
        raise DDError([Finding("LR-S001", f"root element is <{root.tag}>, expected <mxfile>")])
    pages = [_page(pid, name, m) for pid, name, m in models]
    return Doc(pages=pages, compressed=compressed, source=source)


def _num(el: ET.Element | None, key: str, default: float = 0.0) -> float:
    if el is None:
        return default
    v = el.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return math.nan


def _page(pid: str, name: str, model: ET.Element) -> DrawPage:
    root = model.find("root")
    cells: dict[str, Cell] = {}
    order: list[str] = []
    if root is None:
        raise DDError([Finding("LR-S001", f"page {name!r} has no <root>")])
    children = list(root)
    if len(children) > MAX_CELLS:
        raise DDError([Finding("LR-S001", f"page {name!r}: cell limit exceeded (max {MAX_CELLS})")])
    dupes: list[str] = []
    for el in children:
        attrs: dict[str, str] = {}
        if el.tag in ("UserObject", "object"):
            attrs = {k: v for k, v in el.attrib.items()}
            inner = el.find("mxCell")
            if inner is None:
                continue
            cid = el.get("id", "")
            value = el.get("label", "")
            cell_el = inner
        elif el.tag == "mxCell":
            cell_el = el
            cid = el.get("id", "")
            value = el.get("value", "")
        else:
            continue
        g = cell_el.find("mxGeometry")
        base, style = parse_style(cell_el.get("style", ""))
        points: list[Point] = []
        offset: Point = (0.0, 0.0)
        if g is not None:
            arr = g.find("Array")
            if arr is not None:
                points = [(_num(p, "x"), _num(p, "y")) for p in arr.findall("mxPoint")]
            for p in g.findall("mxPoint"):
                if p.get("as") == "offset":
                    offset = (_num(p, "x"), _num(p, "y"))
        cell = Cell(
            id=cid,
            parent=cell_el.get("parent", ""),
            vertex=cell_el.get("vertex") == "1",
            edge=cell_el.get("edge") == "1",
            base=base,
            style=style,
            value=value,
            attrs=attrs,
            geom={k: _num(g, k) for k in ("x", "y", "width", "height")} if g is not None else {},
            relative=g is not None and g.get("relative") == "1",
            points=points,
            offset=offset,
            source=cell_el.get("source", ""),
            target=cell_el.get("target", ""),
            visible=cell_el.get("visible", "1") != "0",
        )
        if cid in cells:
            dupes.append(cid)
        cells[cid] = cell
        order.append(cid)
    page = DrawPage(
        pid,
        name,
        _num(model, "pageWidth", 850),
        _num(model, "pageHeight", 1100),
        model.get("background", ""),
        cells,
        order,
    )
    if dupes:
        page.cells["__dupes__"] = Cell("__dupes__", "", False, False, "", {}, ",".join(dupes), {}, {})
    _absolute(page)
    return page


def _origin(page: DrawPage, cid: str, depth: int = 0) -> tuple[float, float]:
    c = page.cells.get(cid)
    if c is None or not c.vertex or depth > 64:
        return 0.0, 0.0
    px, py = _origin(page, c.parent, depth + 1)
    return px + c.geom.get("x", 0.0), py + c.geom.get("y", 0.0)


def _absolute(page: DrawPage) -> None:
    for c in page.cells.values():
        if c.vertex and c.geom:
            ox, oy = _origin(page, c.parent)
            c.abs_box = Box(
                ox + c.geom.get("x", 0.0),
                oy + c.geom.get("y", 0.0),
                c.geom.get("width", 0.0),
                c.geom.get("height", 0.0),
            )
    for c in page.cells.values():
        if not c.edge:
            continue
        ox, oy = _origin(page, c.parent)
        pts = [(x + ox, y + oy) for x, y in c.points]
        s = page.cells.get(c.source)
        t = page.cells.get(c.target)
        start = _port(s, c.style, "exit") if s and s.abs_box else None
        end = _port(t, c.style, "entry") if t and t.abs_box else None
        if start is None and s is not None and s.abs_box is not None:
            start = (s.abs_box.cx, s.abs_box.cy)
        if end is None and t is not None and t.abs_box is not None:
            end = (t.abs_box.cx, t.abs_box.cy)
        path = ([start] if start else []) + pts + ([end] if end else [])
        c.path = path


def _port(cell: Cell, style: dict[str, str], prefix: str) -> Point | None:
    if f"{prefix}X" not in style or f"{prefix}Y" not in style or cell.abs_box is None:
        return None
    try:
        fx = float(style[f"{prefix}X"])
        fy = float(style[f"{prefix}Y"])
    except ValueError:
        return None
    b = cell.abs_box
    return (round(b.x + b.w * fx), round(b.y + b.h * fy))
