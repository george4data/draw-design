"""Typed view of a validated Diagram Spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    id: str
    label: str
    sublabel: str = ""
    role: str = "backend"
    tag: str = ""
    focal: bool = False
    icon: str = ""
    zone: str = ""
    place: dict[str, Any] = field(default_factory=dict)
    pin: dict[str, float] | None = None
    meta: dict[str, str] = field(default_factory=dict)
    index: int = 0


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    label: str = ""
    kind: str = "default"
    bidirectional: bool = False
    from_side: str = ""
    to_side: str = ""
    transit: bool = False
    index: int = 0


@dataclass
class Zone:
    id: str
    label: str
    role: str = "zone"
    parent: str = ""
    icon: str = ""
    index: int = 0


@dataclass
class Callout:
    text: str
    target: str
    corner: str = "tr"


@dataclass
class Spec:
    type: str
    title: str
    description: str
    eyebrow: str = ""
    subtitle: str = ""
    size: str = "doc-inline"
    detail: str = "balanced"
    audience: str = "mixed"
    direction: str = ""
    variant: str = "light"
    sketch: bool = False
    pattern: str = ""
    icon_style: str = ""
    platform: str = ""
    theme_ref: dict[str, str] = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    legend: bool = True
    callouts: list[Callout] = field(default_factory=list)
    ledger: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)


def from_dict(d: dict[str, Any]) -> Spec:
    nodes = [
        Node(
            id=n["id"],
            label=n["label"],
            sublabel=n.get("sublabel", ""),
            role=n.get("role", ""),
            tag=n.get("tag", "").upper(),
            focal=bool(n.get("focal", False)),
            icon=n.get("icon", ""),
            zone=n.get("zone", ""),
            place=dict(n.get("place", {})),
            pin=n.get("pin"),
            meta=dict(n.get("meta", {})),
            index=i,
        )
        for i, n in enumerate(d.get("nodes", []))
    ]
    edges = [
        Edge(
            id=e.get("id", f"e{i + 1}"),
            src=e["from"],
            dst=e["to"],
            label=e.get("label", ""),
            kind=e.get("kind", "default"),
            bidirectional=bool(e.get("bidirectional", False)),
            from_side=e.get("fromSide", ""),
            to_side=e.get("toSide", ""),
            transit=bool(e.get("transit", False)),
            index=i,
        )
        for i, e in enumerate(d.get("edges", []))
    ]
    zones = [
        Zone(
            id=z["id"],
            label=z["label"],
            role=z.get("role", "zone"),
            parent=z.get("parent", ""),
            icon=z.get("icon", ""),
            index=i,
        )
        for i, z in enumerate(d.get("zones", []))
    ]
    callouts = [Callout(c["text"], c["target"], c.get("corner", "tr")) for c in d.get("callouts", [])]
    return Spec(
        type=d["type"],
        title=d["title"],
        description=d["description"],
        eyebrow=d.get("eyebrow", ""),
        subtitle=d.get("subtitle", ""),
        size=d.get("size", "doc-inline"),
        detail=d.get("detail", "balanced"),
        audience=d.get("audience", "mixed"),
        direction=d.get("direction", ""),
        variant=d.get("variant", "light"),
        sketch=bool(d.get("sketch", False)),
        pattern=d.get("pattern", ""),
        icon_style=d.get("iconStyle", ""),
        platform=d.get("platform", ""),
        theme_ref=dict(d.get("theme", {})),
        nodes=nodes,
        edges=edges,
        zones=zones,
        legend=d.get("legend", "auto") != False,  # noqa: E712
        callouts=callouts,
        ledger=dict(d.get("ledger", {})),
        raw=d,
    )
