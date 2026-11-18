"""Accessible SVG post-processing (PRD FR-062): <title>, <desc>, role="img", aria-labelledby."""

from __future__ import annotations

import html
import re
from pathlib import Path

from ddraw.lint.model import load, strip_html


def _meta(drawio: Path) -> tuple[str, str]:
    try:
        doc = load(drawio.read_text(encoding="utf-8"), str(drawio))
    except Exception:
        return drawio.stem, ""
    page = doc.pages[0]
    title = page.cells.get("dd-title")
    if title is None:
        return page.name, ""
    return strip_html(title.value).strip() or page.name, title.attrs.get("dd-description", "")


def add_accessibility(svg_path: Path, drawio: Path) -> None:
    text = svg_path.read_text(encoding="utf-8")
    title, desc = _meta(drawio)
    slug = re.sub(r"[^a-z0-9]+", "-", svg_path.name.lower().replace(".svg", "")).strip("-") or "diagram"
    m = re.search(r"<svg\b[^>]*>", text)
    if not m:
        return
    tag = m.group(0)
    if 'role="img"' in tag:
        return
    new_tag = tag[:-1].rstrip("/") + f' role="img" aria-labelledby="{slug}-title {slug}-desc">'
    inject = (
        f'<title id="{slug}-title">{html.escape(title)}</title>'
        f'<desc id="{slug}-desc">{html.escape(desc or title)}</desc>'
    )
    text = text[: m.start()] + new_tag + inject + text[m.end() :]
    svg_path.write_text(text, encoding="utf-8")
