"""Type registry, presets and budgets loaded from the skill's data directory."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from ddraw.paths import DATA_DIR


@dataclass(frozen=True)
class TypeInfo:
    slug: str
    name: str
    family: str
    grammar: str
    wave: int
    status: str
    feasibility: str
    roles: tuple[str, ...] = ()
    directions: tuple[str, ...] = ("LR", "TB")
    default_direction: str = "LR"
    aliases: tuple[str, ...] = ()
    use_when: str = ""
    budget: dict[str, int] = field(default_factory=dict)
    edge_label_max: int = 14
    upper_labels: bool = True
    self_loops: bool = False
    routing: str = "orthogonal"  # orthogonal | bus
    legend_backend: str = "SERVICE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "family": self.family,
            "grammar": self.grammar,
            "wave": self.wave,
            "status": self.status,
            "feasibility": self.feasibility,
            "roles": list(self.roles),
            "directions": list(self.directions),
            "aliases": list(self.aliases),
            "useWhen": self.use_when,
            "budget": self.budget,
        }


def _load(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def types() -> dict[str, TypeInfo]:
    out: dict[str, TypeInfo] = {}
    for path in sorted((DATA_DIR / "types.d").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        info = TypeInfo(
            slug=raw["slug"],
            name=raw["name"],
            family=raw["family"],
            grammar=raw["grammar"],
            wave=int(raw["wave"]),
            status=raw["status"],
            feasibility=raw["feasibility"],
            roles=tuple(raw.get("roles", [])),
            directions=tuple(raw.get("directions", ["LR", "TB"])),
            default_direction=raw.get("defaultDirection", "LR"),
            aliases=tuple(raw.get("aliases", [])),
            use_when=raw.get("useWhen", ""),
            edge_label_max=int(raw.get("edgeLabelMax", 14)),
            upper_labels=bool(raw.get("upperLabels", True)),
            self_loops=bool(raw.get("selfLoops", False)),
            routing=str(raw.get("routing", "orthogonal")),
            legend_backend=str(raw.get("legendBackend", "SERVICE")),
            budget={k: int(v) for k, v in raw.get("budget", {}).items()},
        )
        if info.slug != path.stem:
            raise ValueError(f"{path.name}: slug {info.slug!r} does not match file name")
        out[info.slug] = info
    return out


def shipped() -> list[TypeInfo]:
    return [t for t in types().values() if t.status == "shipped"]


@lru_cache(maxsize=1)
def presets() -> dict[str, Any]:
    data: dict[str, Any] = _load("presets.json")
    return data


@lru_cache(maxsize=1)
def budgets() -> dict[str, Any]:
    data: dict[str, Any] = _load("budgets.json")
    return data


def type_budget(slug: str, detail: str = "balanced") -> dict[str, int]:
    """Effective budget for a type: universal limits, tightened by the type's own row.

    `faithful` detail raises the node and edge ceilings (zoning becomes mandatory).
    """
    universal = dict(budgets()["universal"])
    info = types().get(slug)
    if info:
        universal.update(info.budget)
    if detail == "faithful":
        d = budgets()["detail"]["faithful"]
        universal["nodes"] = max(universal["nodes"], d["nodes"])
        universal["edges"] = max(universal["edges"], d["edges"])
    elif detail == "simplified":
        d = budgets()["detail"]["simplified"]
        universal["nodes"] = min(universal["nodes"], d["nodes"])
        universal["edges"] = min(universal["edges"], d["edges"])
    return universal
