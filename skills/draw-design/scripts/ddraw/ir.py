"""In-memory intermediate representation produced by layout and routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ddraw.spec.model import Edge, Node, Spec, Zone

Point = tuple[float, float]


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def inflate(self, d: float) -> Box:
        return Box(self.x - d, self.y - d, self.w + 2 * d, self.h + 2 * d)

    def intersects(self, o: Box) -> bool:
        return self.x < o.right and o.x < self.right and self.y < o.bottom and o.y < self.bottom

    def contains(self, o: Box) -> bool:
        return self.x <= o.x and self.y <= o.y and o.right <= self.right and o.bottom <= self.bottom

    def union(self, o: Box) -> Box:
        x, y = min(self.x, o.x), min(self.y, o.y)
        return Box(x, y, max(self.right, o.right) - x, max(self.bottom, o.bottom) - y)

    def moved(self, dx: float, dy: float) -> Box:
        return Box(self.x + dx, self.y + dy, self.w, self.h)


@dataclass
class PNode:
    node: Node
    box: Box
    shape: str = "box"  # box | pill | rhombus | ellipse
    treatment: str = "backend"

    @property
    def id(self) -> str:
        return self.node.id


@dataclass
class PZone:
    zone: Zone
    box: Box
    depth: int = 0


@dataclass
class Port:
    side: str
    x: float
    y: float
    fx: float
    fy: float


@dataclass
class PEdge:
    edge: Edge
    src_port: Port | None = None
    dst_port: Port | None = None
    path: list[Point] = field(default_factory=list)  # absolute, port to port
    label_box: Box | None = None
    label_param: float = 0.0
    label_offset: Point = (0.0, 0.0)


@dataclass
class TextItem:
    id: str
    role: str  # eyebrow | title | subtitle | legend-title | legend-text | callout
    text: str
    box: Box
    align: str = "left"


@dataclass
class LegendItem:
    id: str
    kind: str  # node | edge
    key: str  # treatment or edge kind
    label: str
    swatch: Box
    text: Box


@dataclass
class Page:
    spec: Spec
    preset: dict[str, Any]
    ramp: dict[str, Any]
    direction: str
    frame: Box
    content: Box
    nodes: dict[str, PNode] = field(default_factory=dict)
    zones: dict[str, PZone] = field(default_factory=dict)
    edges: list[PEdge] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    legend: list[LegendItem] = field(default_factory=list)
    legend_rule: Box | None = None
    callouts: list[tuple[TextItem, str]] = field(default_factory=list)
