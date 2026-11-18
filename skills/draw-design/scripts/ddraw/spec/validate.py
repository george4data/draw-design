"""Spec validation: JSON Schema subset, then semantic checks (PRD §9)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ddraw import registry
from ddraw.errors import DDError, Finding
from ddraw.paths import SCHEMAS_DIR
from ddraw.spec.jsonschema import Validator
from ddraw.spec.model import Spec, from_dict

BASE_ROLES = ("backend", "store", "external", "input", "optional", "security")


@lru_cache(maxsize=1)
def _validator() -> Validator:
    schema = json.loads((SCHEMAS_DIR / "spec.schema.json").read_text(encoding="utf-8"))
    return Validator(schema)


def load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DDError([Finding("SPEC-000", f"cannot read {path}: {exc.strerror}")]) from exc
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DDError([Finding("SPEC-000", "YAML specs need PyYAML; use JSON (.dd.json)")]) from exc
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DDError(
                [Finding("SPEC-000", f"invalid JSON at line {exc.lineno} col {exc.colno}: {exc.msg}")]
            ) from exc
    if not isinstance(data, dict):
        raise DDError([Finding("SPEC-004", "spec must be a JSON object", pointer="/")])
    return data


def validate(data: dict[str, Any]) -> tuple[Spec | None, list[Finding]]:
    findings = _validator().validate(data)
    if any(f.severity == "error" for f in findings):
        return None, findings
    spec = from_dict(data)
    findings.extend(semantic(spec))
    if any(f.severity == "error" for f in findings):
        return None, findings
    return spec, findings


def semantic(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    types = registry.types()
    info = types.get(spec.type)
    if info is None:
        shipped = ", ".join(t.slug for t in registry.shipped())
        out.append(
            Finding(
                "SPEC-010",
                f"unknown diagram type {spec.type!r}",
                pointer="/type",
                fix=f"shipped types: {shipped}",
            )
        )
        return out
    if info.status == "planned":
        shipped = ", ".join(t.slug for t in registry.shipped())
        out.append(
            Finding(
                "SPEC-011",
                f"type {spec.type!r} is planned but not implemented yet",
                pointer="/type",
                fix=f"use one of the shipped types: {shipped}",
            )
        )
        return out
    if spec.direction and spec.direction not in info.directions:
        out.append(
            Finding(
                "SPEC-012",
                f"direction {spec.direction} not supported by {spec.type}",
                pointer="/direction",
                fix=f"use one of {', '.join(info.directions)}",
            )
        )

    seen: dict[str, str] = {}
    groups: list[tuple[str, list[str]]] = [
        ("nodes", [n.id for n in spec.nodes]),
        ("zones", [z.id for z in spec.zones]),
        ("edges", [e.id for e in spec.edges]),
    ]
    for kind, ids in groups:
        for i, item_id in enumerate(ids):
            if item_id in seen:
                out.append(
                    Finding(
                        "SPEC-020",
                        f"duplicate id {item_id!r} (also in {seen[item_id]})",
                        pointer=f"/{kind}/{i}/id",
                    )
                )
            seen[item_id] = kind
    node_ids = {n.id for n in spec.nodes}
    zone_ids = {z.id for z in spec.zones}
    roles = set(info.roles) or set(BASE_ROLES)
    default_role = "step" if spec.type == "flowchart" else "backend"
    for i, n in enumerate(spec.nodes):
        if not n.role:
            n.role = default_role
        if n.role not in roles:
            out.append(
                Finding(
                    "SPEC-021",
                    f"role {n.role!r} not valid for {spec.type}",
                    pointer=f"/nodes/{i}/role",
                    fix=f"use one of {', '.join(sorted(roles))}",
                )
            )
        if n.zone and n.zone not in zone_ids:
            out.append(Finding("SPEC-022", f"zone {n.zone!r} does not exist", pointer=f"/nodes/{i}/zone"))
    for i, z in enumerate(spec.zones):
        if z.parent and z.parent not in zone_ids:
            out.append(
                Finding("SPEC-022", f"parent zone {z.parent!r} does not exist", pointer=f"/zones/{i}/parent")
            )
        if not any(n.zone == z.id for n in spec.nodes) and not any(c.parent == z.id for c in spec.zones):
            out.append(Finding("SPEC-025", f"zone {z.id!r} is empty", pointer=f"/zones/{i}", severity="warn"))
    pairs: set[tuple[str, str]] = set()
    for i, e in enumerate(spec.edges):
        for end, key in ((e.src, "from"), (e.dst, "to")):
            if end not in node_ids:
                out.append(
                    Finding("SPEC-023", f"edge endpoint {end!r} is not a node", pointer=f"/edges/{i}/{key}")
                )
        if e.src == e.dst and spec.type not in ("state",):
            out.append(Finding("SPEC-024", "self-loops are not allowed for this type", pointer=f"/edges/{i}"))
        if (e.src, e.dst) in pairs:
            out.append(
                Finding(
                    "SPEC-026",
                    f"duplicate edge {e.src} → {e.dst}",
                    pointer=f"/edges/{i}",
                    severity="warn",
                    fix="merge the two relationships into one labelled edge",
                )
            )
        pairs.add((e.src, e.dst))
    for i, c in enumerate(spec.callouts):
        if c.target not in node_ids:
            out.append(
                Finding(
                    "SPEC-023", f"callout target {c.target!r} is not a node", pointer=f"/callouts/{i}/target"
                )
            )

    budget = registry.type_budget(spec.type, spec.detail)
    accents = sum(1 for n in spec.nodes if n.focal) + sum(1 for e in spec.edges if e.kind == "accent")
    if accents > budget["accent"]:
        out.append(
            Finding(
                "LR-B003",
                f"{accents} accent elements; at most {budget['accent']}",
                pointer="/nodes",
                fix="keep accent on the one or two things the reader must see first",
            )
        )
    if len(spec.nodes) > budget["nodes"]:
        out.append(
            Finding(
                "LR-B001",
                f"{len(spec.nodes)} nodes; budget is {budget['nodes']} for {spec.type} "
                f"at {spec.detail} detail",
                pointer="/nodes",
                fix="merge nodes that travel together, or split into an overview plus a detail diagram",
            )
        )
    if len(spec.edges) > budget["edges"]:
        out.append(
            Finding(
                "LR-B002",
                f"{len(spec.edges)} edges; budget is {budget['edges']}",
                pointer="/edges",
                fix="remove edges the layout already implies",
            )
        )
    if "zones" in budget and len(spec.zones) > budget["zones"]:
        out.append(
            Finding(
                "LR-B005",
                f"{len(spec.zones)} zones; at most {budget['zones']} for {spec.type}",
                pointer="/zones",
            )
        )
    if spec.type == "flowchart":
        for n in spec.nodes:
            if n.role == "decision":
                exits = [e for e in spec.edges if e.src == n.id]
                if len(exits) > budget.get("decisionExits", 3):
                    out.append(
                        Finding(
                            "LR-Y-flowchart-001",
                            f"decision {n.id!r} has {len(exits)} exits; max 3",
                            pointer="/edges",
                        )
                    )
                for e in exits:
                    if not e.label:
                        out.append(
                            Finding(
                                "LR-Y-flowchart-002",
                                f"exit {e.id} of decision {n.id!r} is unlabelled",
                                pointer=f"/edges/{e.index}/label",
                                fix="label every exit, e.g. YES / NO",
                            )
                        )
    return out


def load_spec(path: Path) -> tuple[Spec, list[Finding]]:
    data = load_json(path)
    spec, findings = validate(data)
    if spec is None:
        raise DDError(findings)
    return spec, findings
