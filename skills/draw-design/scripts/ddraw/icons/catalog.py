"""Vendor shape catalog (PRD §10.8.3): lookup, search and style binding for icon ids.

The catalog is built at release time by scripts/build-shape-catalog.py from draw.io's own shape
index and verified by rendering every entry with draw.io Desktop. Ids are `<family>:<name>`
(e.g. `aws4:lambda`, `gcp:cloud_run`). The agent must take ids from `ddraw icons search`:
draw.io silently draws an empty box for an unknown shape name.
"""

from __future__ import annotations

import difflib
import gzip
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ddraw.paths import DATA_DIR

SHAPES_DIR = DATA_DIR / "shapes"
ID_RE = re.compile(r"^([a-z0-9]+):([a-z0-9_]+)$")
# Style keys that position or format a label; icon cells carry no label, so these are dropped.
LABEL_KEYS = {
    "verticalLabelPosition",
    "verticalAlign",
    "align",
    "labelPosition",
    "fontSize",
    "fontStyle",
    "fontColor",
    "fontFamily",
    "html",
    "whiteSpace",
    "spacing",
    "spacingTop",
    "spacingLeft",
    "spacingBottom",
    "spacingRight",
    "points",
    "sketch",
    "labelBackgroundColor",
}


@dataclass(frozen=True)
class Family:
    family: str
    title: str
    platform: str
    current: bool
    recolor: str  # fill | none
    count: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "title": self.title,
            "platform": self.platform,
            "current": self.current,
            "recolor": self.recolor,
            "count": self.count,
            "note": self.note,
        }


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    tags: tuple[str, ...]
    kind: str  # icon | group
    w: float
    h: float
    style: str
    aliases: tuple[str, ...] = ()

    @property
    def family(self) -> str:
        return self.id.split(":", 1)[0]

    @property
    def name(self) -> str:
        return self.id.split(":", 1)[1]

    def to_dict(self, with_style: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "title": self.title, "kind": self.kind}
        if with_style:
            d.update({"tags": list(self.tags), "w": self.w, "h": self.h, "style": self.style})
        return d


@lru_cache(maxsize=1)
def meta() -> dict[str, Any]:
    path = SHAPES_DIR / "families.json"
    if not path.is_file():
        return {"families": [], "preferred": {}, "verifiedWith": ""}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def families() -> dict[str, Family]:
    return {
        r["family"]: Family(
            r["family"],
            r["title"],
            r["platform"],
            bool(r["current"]),
            r["recolor"],
            int(r["count"]),
            r["note"],
        )
        for r in meta()["families"]
    }


def verified_with() -> str:
    return str(meta().get("verifiedWith", ""))


@lru_cache(maxsize=16)
def entries(family: str) -> dict[str, Entry]:
    path = SHAPES_DIR / f"{family}.json.gz"
    if family not in families() or not path.is_file():
        return {}
    rows = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    return {
        r["id"]: Entry(
            r["id"],
            r["title"],
            tuple(r["tags"]),
            r["kind"],
            float(r["w"]),
            float(r["h"]),
            r["style"],
            tuple(r.get("aliases", ())),
        )
        for r in rows
    }


def lookup(icon_id: str) -> Entry | None:
    m = ID_RE.match(icon_id)
    if not m:
        return None
    return entries(m.group(1)).get(icon_id)


def suggest(icon_id: str, limit: int = 3) -> list[str]:
    """Close ids for a did-you-mean: same family first, then the same name in sibling families."""
    fam, _, name = icon_id.partition(":")
    fams = families()
    if fam not in fams:
        close = difflib.get_close_matches(fam, list(fams), n=1, cutoff=0.5)
        fam = close[0] if close else ""
    out: list[str] = []
    if fam:
        names = [e.name for e in entries(fam).values()]
        out += [f"{fam}:{n}" for n in difflib.get_close_matches(name, names, n=limit, cutoff=0.6)]
        if not out:
            out += [e.id for e in search(name.replace("_", " "), family=fam, limit=limit)]
    if fam and not out:
        platform = fams[fam].platform
        for other in fams.values():
            if (
                other.platform == platform
                and other.family != fam
                and f"{other.family}:{name}" in entries(other.family)
            ):
                out.append(f"{other.family}:{name}")
    return out[:limit]


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def search(
    query: str, *, platform: str = "", family: str = "", kind: str = "icon", limit: int = 8
) -> list[Entry]:
    """Rank entries by token overlap with title, name and tags; preferred families win ties."""
    words = _tokens(query)
    if not words:
        return []
    fams = families()
    preferred: dict[str, list[str]] = meta().get("preferred", {})
    scored: list[tuple[float, str, Entry]] = []
    for f in fams.values():
        if (family and f.family != family) or (platform and f.platform != platform):
            continue
        order = preferred.get(f.platform, [])
        fam_bonus = (0.3 if f.current else 0.0) + (
            0.2 * (len(order) - order.index(f.family)) if f.family in order else 0
        )
        for e in entries(f.family).values():
            if kind and e.kind != kind:
                continue
            title = _tokens(e.title)
            name = e.name.split("_")
            score = 0.0
            for w in words:
                if w in name or w in title or w in e.aliases:
                    score += 3
                elif w in e.tags or (any(t.startswith(w) for t in (*name, *title)) and len(w) >= 3):
                    score += 1
            if score == 0:
                continue
            if "_".join(words) == e.name:
                score += 6
            score -= 0.05 * max(0, len(name) - len(words))  # prefer tighter matches
            scored.append((score + fam_bonus, e.id, e))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [e for _, _, e in scored[:limit]]


def cell_style(entry: Entry, mono: str = "") -> str:
    """The icon's draw.io style for an unlabelled child cell; `mono` recolours recolourable families."""
    parts = []
    for part in entry.style.split(";"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        if key in LABEL_KEYS or key in ("movable", "resizable"):
            continue
        if mono and key == "fillColor":
            part = f"fillColor={mono}"
        parts.append(part)
    if mono and not any(p.startswith("fillColor=") for p in parts):
        parts.append(f"fillColor={mono}")
    parts += ["movable=0", "resizable=0"]
    return ";".join(parts) + ";"


def shape_key(style: dict[str, str]) -> tuple[str, str] | None:
    """(family, catalog name) a parsed draw.io style refers to, if it uses a catalogued library."""
    shape, image = style.get("shape", ""), style.get("image", "")
    if image.startswith("img/lib/azure2/"):
        stem = image.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return "azure2", re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    m = re.match(r"mxgraph\.(aws4|gcp2|gcp3|kubernetes)\.(.+)$", shape)
    if not m:
        return None
    fam, sub = m.group(1), m.group(2)
    for key in ("resIcon", "grIcon", "prIcon"):
        if style.get(key):
            return fam, style[key].rsplit(".", 1)[-1].lower()
    return fam, sub.lower()


@lru_cache(maxsize=1)
def known_keys() -> frozenset[tuple[str, str]]:
    """Every (family, name) the verified catalog can draw, keyed the way `shape_key` reads a style."""
    out: set[tuple[str, str]] = set()
    for fam in ("aws4", "gcp2", "gcp3", "kubernetes", "azure2"):
        for e in entries(fam).values():
            parsed = dict(p.split("=", 1) for p in e.style.split(";") if "=" in p)
            if "image" in e.style and fam == "azure2":
                parsed.setdefault("shape", "image")
            k = shape_key(parsed)
            if k:
                out.add(k)
    return frozenset(out)


def recolorable(icon_id: str) -> bool:
    f = families().get(icon_id.split(":", 1)[0])
    return f is not None and f.recolor != "none"
