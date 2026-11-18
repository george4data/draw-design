"""Restyle an existing draw.io file to the theme, keeping its geometry (PRD §13.2 FR-073)."""

from __future__ import annotations

import colorsys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ddraw.errors import DDError, Finding
from ddraw.lint.model import _reject_unsafe, decompress, parse_style
from ddraw.theme import color
from ddraw.theme.model import Theme

DROP = {"shadow", "glass", "gradientColor", "gradientDirection", "comic", "sketch", "jiggle", "curveFitting"}
RECT_SHAPES = {"", "rounded", "rect", "process", "label"}
SHAPE_TREATMENT = {"cylinder": "store", "datastore": "store", "note": "optional", "cloud": "external"}


@dataclass
class Report:
    vertices: int = 0
    edges: int = 0
    containers: int = 0
    texts: int = 0
    kept: list[str] = field(default_factory=list)
    mapping: dict[str, int] = field(default_factory=dict)
    focal: list[str] = field(default_factory=list)
    snapped: bool = False

    def markdown(self, src: str, out: str) -> str:
        lines = [
            f"# Restyle report: {src}",
            "",
            f"Output: `{out}`",
            "",
            f"- {self.vertices} shapes, {self.edges} connectors, {self.containers} containers, "
            f"{self.texts} text cells restyled",
        ]
        if self.mapping:
            lines.append(
                "- Colour → treatment: " + ", ".join(f"{k} ×{v}" for k, v in sorted(self.mapping.items()))
            )
        if self.focal:
            lines.append(f"- Focal (accent): {', '.join(self.focal)}")
        if self.kept:
            lines.append(
                f"- Left as drawn (icons, images, vendor stencils): {', '.join(sorted(set(self.kept))[:12])}"
            )
        snap = " except snapping to the 4px grid" if self.snapped else ""
        lines.append(f"- Removed: shadows, glass, gradients. Geometry is unchanged{snap}.")
        return "\n".join(lines) + "\n"


def treatment_for(fill: str) -> str:
    """Map a source fill colour to a semantic treatment (reference import-drawio colour table)."""
    if not fill or fill in ("none", "default", "inherit"):
        return "backend"
    try:
        (r, g, b), _ = color.parse(fill)
    except ValueError:
        return "backend"
    h, lum, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if s < 0.15:
        return "store" if lum < 0.97 else "backend"
    hue = h * 360
    if hue >= 330 or hue < 20:
        return "optional"  # red: failure / risk / legacy
    if 250 <= hue < 330:
        return "external"  # purple: third party
    return "backend"


def _fmt(style: dict[str, str], base: str) -> str:
    parts = ([base] if base else []) + [f"{k}={v}" for k, v in style.items()]
    return ";".join(parts) + ";"


def _snap(geom: ET.Element) -> None:
    for k in ("x", "y", "width", "height"):
        v = geom.get(k)
        if v is not None:
            try:
                geom.set(k, str(int(round(float(v) / 4) * 4)))
            except ValueError:
                continue


def restyle_text(
    text: str, theme: Theme, *, snap: bool = False, focal: set[str] | None = None, orthogonal: bool = True
) -> tuple[str, Report]:
    focal = focal or set()
    _reject_unsafe(text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DDError([Finding("IMPORT-001", f"not a draw.io file: {exc}")]) from exc
    if root.tag != "mxfile":
        raise DDError([Finding("IMPORT-001", f"root element is <{root.tag}>, expected <mxfile>")])
    report = Report(snapped=snap)
    root.set("compressed", "false")
    from ddraw.emit import styles  # local import: emitter depends on theme only

    for diagram in root.findall("diagram"):
        model = diagram.find("mxGraphModel")
        if model is None and (diagram.text or "").strip():
            inner = decompress((diagram.text or "").strip())
            _reject_unsafe(inner)
            model = ET.fromstring(inner)
            diagram.text = None
            diagram.append(model)
        if model is None:
            continue
        model.set("background", theme.c("paper"))
        model.set("adaptiveColors", "none")
        cells = model.find("root")
        if cells is None:
            continue
        cells_by_id: dict[str, ET.Element] = {}
        for el in cells:
            found = el.find("mxCell") if el.tag in ("UserObject", "object") else el
            if found is not None:
                cells_by_id[el.get("id", "")] = found
        for el in list(cells):
            cell = el.find("mxCell") if el.tag in ("UserObject", "object") else el
            if cell is None:
                continue
            cid = el.get("id", "")
            base, st = parse_style(cell.get("style", ""))
            for k in DROP:
                st.pop(k, None)
            geom = cell.find("mxGeometry")
            if snap and geom is not None and cell.get("vertex") == "1":
                _snap(geom)
            if cell.get("edge") == "1":
                report.edges += 1
                kind = "accent" if cid in focal else "default"
                stroke = theme.c("accent") if kind == "accent" else theme.c("muted")
                if orthogonal and st.get("edgeStyle", "none") in ("none", "") and not st.get("curved"):
                    st["edgeStyle"] = "orthogonalEdgeStyle"
                st.update(
                    {
                        "rounded": "1",
                        "strokeColor": stroke,
                        "strokeWidth": "1.2" if kind == "accent" else "1",
                        "jumpStyle": "arc",
                        "jumpSize": "8",
                        "fontFamily": theme.font("mono"),
                        "fontColor": theme.c("soft"),
                        "labelBackgroundColor": theme.c("paper"),
                        "endSize": "6",
                    }
                )
                if st.get("endArrow", "classic") in ("classic", "classicThin", "block"):
                    st["endArrow"] = "block"
                    st["endFill"] = "1"
                cell.set("style", _fmt(st, base))
                continue
            if cell.get("vertex") != "1":
                continue
            shape = st.get("shape", "")
            parent = cells_by_id.get(cell.get("parent", ""))
            if base == "edgeLabel" or (parent is not None and parent.get("edge") == "1"):
                report.texts += 1
                st.update(
                    {
                        "fontFamily": theme.font("mono"),
                        "fontColor": theme.c("soft"),
                        "labelBackgroundColor": theme.c("paper"),
                    }
                )
                cell.set("style", _fmt(st, base))
                continue
            if base in ("text",) or st.get("text") == "1":
                report.texts += 1
                size = float(st.get("fontSize", "12") or 12)
                st["fontFamily"] = theme.font("title") if size >= 20 else theme.font("sans")
                st["fontColor"] = theme.c("ink")
                cell.set("style", _fmt(st, base))
                continue
            if base == "image" or shape == "image" or shape.startswith("mxgraph.") or "image" in st:
                report.kept.append(shape or base or "image")
                continue
            if base == "swimlane" or st.get("container") == "1" or base == "group":
                report.containers += 1
                if base != "group":
                    st.update(
                        {
                            "fillColor": theme.c("ink", 0.02),
                            "strokeColor": theme.c("ink", 0.20),
                            "fontColor": theme.c("soft"),
                            "fontFamily": theme.font("mono"),
                            "rounded": "1",
                            "arcSize": "8",
                            "absoluteArcSize": "1",
                            "strokeWidth": "0.8",
                        }
                    )
                    if base == "swimlane":
                        st["swimlaneFillColor"] = theme.c("ink", 0.02)
                cell.set("style", _fmt(st, base))
                continue
            report.vertices += 1
            by_shape = next((v for k, v in SHAPE_TREATMENT.items() if (shape or base).startswith(k)), "")
            name = "focal" if cid in focal else (by_shape or treatment_for(st.get("fillColor", "")))
            report.mapping[name] = report.mapping.get(name, 0) + 1
            if cid in focal:
                report.focal.append(cid)
            treat = dict(styles.treatment(theme, name))
            keep_shape = base not in RECT_SHAPES or shape not in RECT_SHAPES
            for k, v in treat.items():
                if keep_shape and k in ("rounded", "arcSize", "absoluteArcSize"):
                    continue
                st[k] = v
            st["fontFamily"] = theme.font("sans")
            cell.set("style", _fmt(st, base))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n", report


def restyle_file(
    src: Path,
    out: Path | None,
    theme: Theme,
    *,
    snap: bool = False,
    focal: set[str] | None = None,
    orthogonal: bool = True,
) -> tuple[Path, Report]:
    try:
        text = src.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DDError([Finding("IMPORT-001", f"cannot read {src}: {exc}")]) from exc
    xml, report = restyle_text(text, theme, snap=snap, focal=focal, orthogonal=orthogonal)
    stem = src.name[: -len(".drawio")] if src.name.endswith(".drawio") else src.stem
    target = out or src.with_name(f"{stem}.restyled.drawio")
    target.write_text(xml, encoding="utf-8")
    return target, report
