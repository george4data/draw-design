"""Run lint rules over a .drawio document."""

from __future__ import annotations

from pathlib import Path

from ddraw import registry
from ddraw.errors import DDError, Finding
from ddraw.lint.model import Doc, load
from ddraw.lint.rules import RULES, Context
from ddraw.theme.model import Theme, load_theme
from ddraw.theme.resolve import profile_path


def context_for(doc: Doc, theme: Theme | None) -> Context:
    page = doc.pages[0]
    title = page.cells.get("dd-title")
    attrs = title.attrs if title else {}
    compiled = "dd-version" in attrs
    if theme is None and compiled:
        slug = attrs.get("dd-theme", "default")
        path = profile_path(slug) if slug != "default" else None
        if path is None or path.exists():
            theme = load_theme(path)
    size = attrs.get("dd-size", "doc-inline")
    preset = registry.presets()["presets"].get(size, {"safe": 40})
    return Context(
        theme=theme,
        compiled=compiled,
        dtype=attrs.get("dd-type", ""),
        detail=attrs.get("dd-detail", "balanced"),
        safe=int(preset.get("safe", 40)),
    )


def lint_doc(doc: Doc, theme: Theme | None = None, only: list[str] | None = None) -> list[Finding]:
    ctx = context_for(doc, theme)
    findings: list[Finding] = []
    for page in doc.pages:
        for rule in RULES:
            for f in rule(page, ctx):
                if only and not any(f.code.startswith(o.rstrip("*")) for o in only):
                    continue
                if len(doc.pages) > 1 and f.cell:
                    f.cell = f"{page.name}:{f.cell}"
                findings.append(f)
    if doc.compressed:
        findings.append(
            Finding("LR-S006", "diagram is compressed; uncompressed XML is diff-friendly", severity="warn")
        )
    return findings


def lint_text(
    text: str, theme: Theme | None = None, source: str = "<input>", only: list[str] | None = None
) -> list[Finding]:
    try:
        doc = load(text, source)
    except DDError as exc:
        return exc.findings
    return lint_doc(doc, theme, only)


def lint_file(path: Path, theme: Theme | None = None, only: list[str] | None = None) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [Finding("LR-S001", f"cannot read {path}: {exc}")]
    return lint_text(text, theme, str(path), only)
