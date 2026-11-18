"""validate → theme → size → layout → route → page → emit → lint (PRD §7.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ddraw import registry
from ddraw.emit import mxgraph
from ddraw.errors import DDError, Finding
from ddraw.ir import Box, Page, PEdge, TextItem
from ddraw.layout import bands, lanes, layered, sequence, sizing, tree
from ddraw.layout import page as page_mod
from ddraw.lint.runner import lint_text
from ddraw.route import router
from ddraw.spec.model import Spec
from ddraw.spec.validate import validate
from ddraw.text.measure import ceil4, width
from ddraw.theme.model import Theme, load_theme
from ddraw.theme.resolve import profile_path, resolve

VIRTUAL = 4000


@dataclass
class BuildResult:
    xml: str
    page: Page
    theme: Theme
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


def pick_theme(
    spec: Spec, *, project: Path | None, theme_path: Path | None, profile: str | None, adaptive: bool
) -> Theme:
    primary = "dark" if spec.variant == "dark" else "light"
    # A dark variant is a fixed dark rendering; the light variant adapts to the viewer's mode.
    adaptive = adaptive and primary == "light"
    if theme_path:
        return load_theme(theme_path, adaptive=adaptive, primary=primary)
    slug = profile or spec.theme_ref.get("profile")
    if spec.theme_ref.get("path") and project:
        return load_theme((project / spec.theme_ref["path"]).resolve(), adaptive=adaptive, primary=primary)
    if slug and slug != "default":
        p = profile_path(slug)
        if p is None or not p.is_file():
            raise DDError(
                [Finding("THEME-002", f"profile {slug!r} not found", fix="run: ddraw profile list")]
            )
        return load_theme(p, adaptive=adaptive, primary=primary)
    if slug == "default":
        return load_theme(None, adaptive=adaptive, primary=primary)
    if project is not None:
        res = resolve(project)
        if res.status in ("profile", "custom-unsaved") and res.path:
            return load_theme(res.path, adaptive=adaptive, primary=primary)
    return load_theme(None, adaptive=adaptive, primary=primary)


def resolve_theme_for(project: Path | None, profile: str | None = None) -> Theme:
    """Theme for operations without a spec (import, library): profile > project marker > default."""
    if profile and profile != "default":
        p = profile_path(profile)
        if p is None or not p.is_file():
            raise DDError(
                [Finding("THEME-002", f"profile {profile!r} not found", fix="run: ddraw profile list")]
            )
        return load_theme(p)
    if project is not None and profile != "default":
        res = resolve(project)
        if res.status in ("profile", "custom-unsaved") and res.path:
            return load_theme(res.path)
    return load_theme(None)


YES = {"YES", "Y", "TRUE", "OK", "PASS"}
NO = {"NO", "N", "FALSE", "FAIL"}


def type_conventions(spec: Spec, direction: str) -> dict[str, float]:
    """Type grammar defaults (only where the spec gave no hint). Returns order-axis bias per node.

    Flowchart: YES exits right, NO exits below. In TB the YES target sits to the right of the
    decision; in LR the NO target sits below it.
    """
    bias: dict[str, float] = {}
    if spec.type == "flowchart":
        decisions = {n.id for n in spec.nodes if n.role == "decision"}
        tb = direction in ("TB", "BT")
        for e in spec.edges:
            if e.src not in decisions:
                continue
            if e.label in YES:
                if not e.from_side:
                    e.from_side = "right"
                if tb:
                    bias[e.dst] = bias.get(e.dst, 0.0) + 1.0
            elif e.label in NO:
                if not e.from_side:
                    e.from_side = "bottom"
                if not tb:
                    bias[e.dst] = bias.get(e.dst, 0.0) + 1.0
    return bias


def compose(spec: Spec, theme: Theme) -> Page:
    presets = registry.presets()
    preset = dict(presets["presets"][spec.size])
    ramp = dict(presets["ramps"][preset["ramp"]])
    info = registry.types()[spec.type]
    direction = spec.direction or info.default_direction
    fit = spec.size == "fit"
    safe = int(preset["safe"])
    fw, fh = (VIRTUAL, VIRTUAL) if fit else (preset["width"], preset["height"])
    frame = Box(0, 0, fw, fh)
    page = Page(spec=spec, preset=preset, ramp=ramp, direction=direction, frame=frame, content=frame)
    page.nodes = sizing.size_nodes(spec.nodes, ramp)
    page.edges = [PEdge(edge=e) for e in spec.edges]
    content_top = page_mod.header(page)
    nodes_legend, edges_legend = page_mod.legend_items(page)
    has_legend = spec.legend and bool(nodes_legend or edges_legend)
    rows = page_mod.legend_rows(page, fw if not fit else 1280) if has_legend else 0
    strip = page_mod.strip_height(rows)
    bottom = fh - safe - (strip + 16 if has_legend else 0)
    if spec.callouts:
        content_top += 24
    area = Box(safe, content_top, fw - 2 * safe, bottom - content_top)
    page.content = area
    if info.grammar == "bands":
        bands.layout(spec, page.nodes, area, ramp, fit)
    elif info.grammar == "lifelines":
        sequence.layout(page, area, fit)
    elif info.grammar == "lanes":
        page.zones = lanes.layout(spec, page.nodes, area, ramp, fit)
    elif info.grammar == "tree":
        try:
            tree.layout(spec, page.nodes, area, direction, fit)
        except DDError:
            alt = next((d for d in info.directions if d != direction), "")
            if spec.direction or not alt:
                raise
            direction = page.direction = alt
            tree.layout(spec, page.nodes, area, direction, fit)
    elif info.grammar == "layered":
        try:
            page.zones = layered.layout(
                spec, page.nodes, area, direction, ramp, fit=fit, bias=type_conventions(spec, direction)
            )
        except DDError as exc:
            alt = next((d for d in info.directions if d != direction), "")
            if spec.direction or not alt or not any(f.code == "LAYOUT-001" for f in exc.findings):
                raise
            direction = page.direction = alt
            page.nodes = sizing.size_nodes(spec.nodes, ramp)
            for e in spec.edges:
                e.from_side = next(
                    (
                        x["fromSide"]
                        for i, x in enumerate(spec.raw.get("edges", []))
                        if i == e.index and "fromSide" in x
                    ),
                    "",
                )
            try:
                page.zones = layered.layout(
                    spec, page.nodes, area, direction, ramp, fit=fit, bias=type_conventions(spec, direction)
                )
            except DDError as exc2:
                exc2.findings[0].message += f" (also tried {info.default_direction})"
                raise
    else:
        raise DDError([Finding("LAYOUT-000", f"no layout engine for grammar {info.grammar!r} yet")])
    if fit:
        boxes = [pn.box for pn in page.nodes.values()] + [z.box for z in page.zones.values()]
        boxes += [x.box for x in page.extras if not x.parent]
        right = max(b.right for b in boxes)
        lowest = max(b.bottom for b in boxes)
        title_w = max((t.box.right for t in page.texts), default=0)
        fw = ceil4(max(right, title_w) + safe)
        if has_legend:
            fw = max(fw, min(ceil4(safe + page_mod.legend_natural_width(page) + safe), 1280))
            strip = page_mod.strip_height(page_mod.legend_rows(page, fw))
        fh = ceil4(lowest + 24 + strip + safe)
        page.frame = Box(0, 0, fw, fh)
        page.content = Box(safe, content_top, fw - 2 * safe, lowest - content_top)
    if not page.prerouted:
        router.route(page.edges, page.nodes, page.frame.inflate(-8), direction, ramp, mode=info.routing)
    if has_legend:
        page_mod.legend(page, page.frame.h - safe - strip)
    for i, c in enumerate(spec.callouts):
        tw = ceil4(width(c.text, 14, "serif") + 8)
        right = c.corner in ("tr", "br")
        x = page.frame.right - safe - tw if right else page.frame.x + safe
        y = page.content.y - 28 if c.corner in ("tl", "tr") else page.content.bottom + 4
        page.callouts.append(
            (
                TextItem(
                    f"callout-{i + 1}", "callout", c.text, Box(x, y, tw, 20), "right" if right else "left"
                ),
                c.target,
            )
        )
    return page


def build(
    data: dict[str, Any],
    *,
    project: Path | None = None,
    theme_path: Path | None = None,
    profile: str | None = None,
    adaptive: bool = True,
    run_lint: bool = True,
) -> BuildResult:
    spec, findings = validate(data)
    if spec is None:
        raise DDError(findings)
    theme = pick_theme(spec, project=project, theme_path=theme_path, profile=profile, adaptive=adaptive)
    page = compose(spec, theme)
    xml = mxgraph.write(page, theme)
    if run_lint:
        findings.extend(lint_text(xml, theme, "<build>"))
    return BuildResult(xml=xml, page=page, theme=theme, findings=findings)
