"""Theme-bound draw.io style strings (PRD §10.3). Only allowlisted keys are emitted."""

from __future__ import annotations

from ddraw.theme.model import Theme

ALLOWED = {
    # vertex
    "shape",
    "rounded",
    "arcSize",
    "absoluteArcSize",
    "whiteSpace",
    "html",
    "fillColor",
    "strokeColor",
    "strokeWidth",
    "dashed",
    "dashPattern",
    "opacity",
    "fillOpacity",
    "strokeOpacity",
    "textOpacity",
    "fontFamily",
    "fontSize",
    "fontColor",
    "fontStyle",
    "fontSource",
    "align",
    "verticalAlign",
    "labelPosition",
    "verticalLabelPosition",
    "spacing",
    "spacingTop",
    "spacingBottom",
    "spacingLeft",
    "spacingRight",
    "labelBackgroundColor",
    "labelBorderColor",
    "overflow",
    "horizontal",
    "container",
    "collapsible",
    "pointerEvents",
    "startSize",
    "swimlaneFillColor",
    "childLayout",
    "perimeter",
    "aspect",
    "image",
    "imageAspect",
    "imageWidth",
    "imageHeight",
    "shadow",
    "sketch",
    "curveFitting",
    "jiggle",
    "fillStyle",
    "points",
    "portConstraint",
    "direction",
    "rotation",
    "flipH",
    "flipV",
    "size",
    "editable",
    "movable",
    "resizable",
    "deletable",
    "locked",
    "selectable",
    # edge
    "edgeStyle",
    "elbow",
    "curved",
    "orthogonalLoop",
    "jettySize",
    "jumpStyle",
    "jumpSize",
    "startArrow",
    "endArrow",
    "startFill",
    "endFill",
    "endSize",
    "exitX",
    "exitY",
    "exitDx",
    "exitDy",
    "exitPerimeter",
    "entryX",
    "entryY",
    "entryDx",
    "entryDy",
    "entryPerimeter",
    "flowAnimation",
}
BARE = {"text", "ellipse", "rhombus", "line", "edgeLabel"}

Style = list[tuple[str, str]]


def fmt(v: float | int | str) -> str:
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return str(v)


def render(base: str, pairs: Style) -> str:
    parts = [base] if base else []
    for k, v in pairs:
        if k not in ALLOWED:
            raise ValueError(f"style key {k!r} is not on the allowlist")
        parts.append(f"{k}={v}")
    return ";".join(parts) + ";"


def treatment(theme: Theme, name: str, sketch: bool = False) -> Style:
    stroke_w = theme.raw["stroke"]
    r = theme.raw["radius"]["md"]
    common: Style = [
        ("rounded", "1"),
        ("arcSize", str(r)),
        ("absoluteArcSize", "1"),
        ("whiteSpace", "wrap"),
        ("html", "1"),
        ("shadow", "0"),
    ]
    fill: dict[str, tuple[str, str, float, str]] = {
        # name: (fill, stroke, width, dash)
        "focal": (theme.c("accent", 0.08), theme.c("accent"), stroke_w["strong"], ""),
        "backend": (theme.c("nodeFill"), theme.c("ink"), stroke_w["default"], ""),
        "store": (theme.c("ink", 0.05), theme.c("muted"), stroke_w["default"], ""),
        "external": (theme.c("ink", 0.03), theme.c("ink", 0.30), stroke_w["default"], ""),
        "input": (theme.c("muted", 0.10), theme.c("soft"), stroke_w["default"], ""),
        "optional": (theme.c("ink", 0.02), theme.c("ink", 0.20), stroke_w["default"], "4 3"),
        "security": (theme.c("accent", 0.05), theme.c("accent", 0.50), stroke_w["default"], "4 4"),
    }
    f, s, w, dash = fill[name]
    out = [*common, ("fillColor", f), ("strokeColor", s), ("strokeWidth", fmt(float(w)))]
    if dash:
        out += [("dashed", "1"), ("dashPattern", dash)]
    out += [("fontColor", theme.c("ink"))]
    if sketch:
        out += [("sketch", "1"), ("curveFitting", "1"), ("jiggle", "2")]
    return out


def node_style(theme: Theme, treatment_name: str, shape: str, has_tag: bool, sketch: bool, h: float) -> str:
    pairs = treatment(theme, treatment_name, sketch)
    base = ""
    if shape == "pill":
        pairs = [(k, str(int(h // 2)) if k == "arcSize" else v) for k, v in pairs]
    elif shape == "rhombus":
        base = "rhombus"
        pairs = [(k, v) for k, v in pairs if k not in ("rounded", "arcSize", "absoluteArcSize")]
        pairs += [("perimeter", "rhombusPerimeter")]
    elif shape in ("dot", "ring"):
        base = "ellipse" if shape == "dot" else ""
        drop = ("rounded", "arcSize", "absoluteArcSize", "fillColor", "strokeColor")
        pairs = [(k, v) for k, v in pairs if k not in drop]
        pairs += [
            ("fillColor", theme.c("ink")),
            ("strokeColor", theme.c("ink")),
            ("perimeter", "ellipsePerimeter"),
        ]
        if shape == "ring":
            pairs += [("shape", "doubleEllipse")]
    elif shape == "state":
        pairs = [(k, str(theme.raw["radius"]["lg"]) if k == "arcSize" else v) for k, v in pairs]
    elif shape == "ellipse":
        base = "ellipse"
        pairs = [(k, v) for k, v in pairs if k not in ("rounded", "arcSize", "absoluteArcSize")]
        pairs += [("perimeter", "ellipsePerimeter")]
    pairs += [("align", "center"), ("verticalAlign", "middle"), ("spacing", "4")]
    if has_tag:
        pairs += [("spacingTop", "12")]
    return render(base, pairs)


def tag_style(theme: Theme, treatment_name: str) -> str:
    stroke_role = "accent" if treatment_name in ("focal", "security") else "ink"
    return render(
        "",
        [
            ("rounded", "1"),
            ("arcSize", "2"),
            ("absoluteArcSize", "1"),
            ("html", "1"),
            ("whiteSpace", "nowrap"),
            ("fillColor", "none"),
            ("strokeColor", theme.c(stroke_role, 0.40)),
            ("strokeWidth", "0.8"),
            ("fontFamily", theme.font("mono")),
            ("fontSize", "7"),
            ("fontColor", theme.c(stroke_role, 0.80)),
            ("align", "center"),
            ("verticalAlign", "middle"),
            ("spacing", "0"),
            ("shadow", "0"),
            ("movable", "0"),
            ("resizable", "0"),
        ],
    )


def zone_style(theme: Theme, role: str, depth: int) -> str:
    over = "paper"
    fill = theme.c("ink", 0.02 + 0.01 * depth, over)
    stroke = theme.c("accent", 0.50) if role == "security" else theme.c("ink", 0.20)
    pairs: Style = [
        ("rounded", "1"),
        ("arcSize", str(theme.raw["radius"]["lg"])),
        ("absoluteArcSize", "1"),
        ("container", "1"),
        ("collapsible", "0"),
        ("pointerEvents", "0"),
        ("html", "1"),
        ("whiteSpace", "nowrap"),
        ("fillColor", fill),
        ("strokeColor", stroke),
        ("strokeWidth", "0.8"),
        ("shadow", "0"),
        ("align", "left"),
        ("verticalAlign", "top"),
        ("spacingLeft", "12"),
        ("spacingTop", "6"),
        ("fontFamily", theme.font("mono")),
        ("fontSize", "8"),
        ("fontColor", theme.c("soft")),
    ]
    if role == "security":
        pairs += [("dashed", "1"), ("dashPattern", "4 4")]
    return render("", pairs)


EDGE_KINDS = ("default", "accent", "link", "async", "return")


def edge_style(
    theme: Theme,
    kind: str,
    ports: tuple[float, float, float, float],
    bidirectional: bool,
    transit: bool,
    ramp_arrow: int,
) -> str:
    sx, sy, tx, ty = ports
    stroke = {
        "default": theme.c("muted"),
        "accent": theme.c("accent"),
        "link": theme.c("link"),
        "async": theme.c("muted"),
        "return": theme.c("soft"),
    }[kind]
    w = 1.2 if kind == "accent" else 1.0
    end_arrow, end_fill = ("open", "0") if kind == "async" else ("block", "1")
    pairs: Style = [
        ("edgeStyle", "orthogonalEdgeStyle"),
        ("rounded", "1"),
        ("orthogonalLoop", "1"),
        ("jettySize", "auto"),
        ("html", "1"),
        ("strokeColor", stroke),
        ("strokeWidth", fmt(w)),
        ("endArrow", end_arrow),
        ("endFill", end_fill),
        ("endSize", "6"),
        ("startArrow", end_arrow if bidirectional else "none"),
        ("startFill", end_fill if bidirectional else "0"),
        ("startSize", "6"),
        ("exitX", fmt(sx)),
        ("exitY", fmt(sy)),
        ("exitDx", "0"),
        ("exitDy", "0"),
        ("exitPerimeter", "0"),
        ("entryX", fmt(tx)),
        ("entryY", fmt(ty)),
        ("entryDx", "0"),
        ("entryDy", "0"),
        ("entryPerimeter", "0"),
        ("jumpStyle", "arc"),
        ("jumpSize", "8"),
        ("fontFamily", theme.font("mono")),
        ("fontSize", str(ramp_arrow)),
        ("fontColor", theme.c("soft")),
        ("labelBackgroundColor", theme.c("paper")),
        ("spacing", "2"),
    ]
    if kind in ("async", "return") or transit:
        pairs += [("dashed", "1"), ("dashPattern", "4 3" if transit else "5 4")]
    return render("", pairs)


def text_style(theme: Theme, role: str, size: int, align: str = "left") -> str:
    family = {
        "title": theme.font("title"),
        "subtitle": theme.font("sans"),
        "callout": theme.font("callout"),
    }.get(role, theme.font("mono"))
    color = {
        "title": theme.c("ink"),
        "subtitle": theme.c("muted"),
        "callout": theme.c("ink"),
        "legend-title": theme.c("muted"),
    }.get(role, theme.c("soft"))
    pairs: Style = [
        ("html", "1"),
        ("whiteSpace", "nowrap"),
        ("align", align),
        ("verticalAlign", "middle"),
        ("fontFamily", family),
        ("fontSize", str(size)),
        ("fontColor", color),
        ("spacing", "0"),
        ("fillColor", "none"),
        ("strokeColor", "none"),
    ]
    if role == "callout":
        pairs.append(("fontStyle", "2"))
    return render("text", pairs)


def legend_swatch(theme: Theme, kind: str, key: str) -> str:
    if kind == "node":
        pairs = [(k, "2" if k == "arcSize" else v) for k, v in treatment(theme, key)]
        return render("", [*pairs, ("movable", "1")])
    stroke = {
        "default": theme.c("muted"),
        "accent": theme.c("accent"),
        "link": theme.c("link"),
        "async": theme.c("muted"),
        "return": theme.c("soft"),
    }[key]
    pairs2: Style = [
        ("html", "1"),
        ("strokeColor", stroke),
        ("strokeWidth", "1.2" if key == "accent" else "1"),
    ]
    if key in ("async", "return"):
        pairs2 += [("dashed", "1"), ("dashPattern", "5 4")]
    return render("line", pairs2)


def rule_style(theme: Theme) -> str:
    return render("line", [("html", "1"), ("strokeColor", theme.c("ink", 0.12)), ("strokeWidth", "0.8")])


def frame_style() -> str:
    return render(
        "",
        [
            ("fillColor", "none"),
            ("strokeColor", "none"),
            ("strokeWidth", "0"),
            ("html", "1"),
            ("locked", "1"),
            ("selectable", "0"),
        ],
    )
