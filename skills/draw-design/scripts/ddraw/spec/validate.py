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
    default_role = {"flowchart": "step", "state": "state"}.get(spec.type, "backend")
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
        if e.src == e.dst and not info.self_loops:
            out.append(Finding("SPEC-024", "self-loops are not allowed for this type", pointer=f"/edges/{i}"))
        if (e.src, e.dst) in pairs and info.grammar != "lifelines":
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

    for i, e in enumerate(spec.edges):
        if info.upper_labels:
            e.label = e.label.upper()
        if len(e.label) > info.edge_label_max:
            out.append(
                Finding(
                    "LR-C007",
                    f"edge label {e.label!r} is longer than {info.edge_label_max} characters",
                    pointer=f"/edges/{i}/label",
                    fix="shorten it or drop it if the layout implies it",
                )
            )
    if info.routing == "bus":
        out.extend(_tree_checks(spec))
    if info.grammar == "lifelines":
        out.extend(_sequence_checks(spec, info))
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
    out += _icon_checks(spec, info)
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


ICON_EXEMPT_ROLES = {"external", "input", "actor"}


def _icon_checks(spec: Spec, info: registry.TypeInfo) -> list[Finding]:
    """Vendor icon ids, family discipline and placement rules (PRD §10.8, LR-I001–I005)."""
    from ddraw.icons import catalog

    out: list[Finding] = []
    base = "/sequence/participants" if spec.type == "sequence" else "/nodes"
    for i, z in enumerate(spec.zones):
        if z.icon:
            out.append(
                Finding(
                    "SPEC-031",
                    "zone icons (vendor group containers such as an AWS VPC) are planned, not built yet",
                    pointer=f"/zones/{i}/icon",
                    fix="remove the zone icon; the zone keeps its editorial style",
                )
            )
    used = [n for n in spec.nodes if n.icon]
    if not used:
        if spec.icon_style:
            out.append(
                Finding(
                    "SPEC-033",
                    "iconStyle has no effect without node icons",
                    severity="warn",
                    pointer="/iconStyle",
                )
            )
        return out
    if not info.icons:
        typed = ", ".join(t.slug for t in registry.shipped() if t.icons)
        return [
            *out,
            Finding(
                "SPEC-030",
                f"{spec.type} diagrams do not use icons",
                pointer=f"{base}/{used[0].index}/icon",
                fix=f"remove the icons; they are for {typed}",
            ),
        ]
    fams = catalog.families()
    by_platform: dict[str, set[str]] = {}
    used_families: set[str] = set()
    for n in used:
        ptr = f"{base}/{n.index}/icon"
        entry = catalog.lookup(n.icon)
        if entry is None:
            if ":" not in n.icon:
                fix = "generic bundled icons are planned; use a vendor id from `ddraw icons search`"
            else:
                close = catalog.suggest(n.icon)
                fix = (
                    f"did you mean {' or '.join(close)}?"
                    if close
                    else "find the id with `ddraw icons search`"
                )
            out.append(Finding("LR-I001", f"unknown icon {n.icon!r}", pointer=ptr, fix=fix))
            continue
        if entry.kind != "icon":
            out.append(
                Finding(
                    "LR-I001",
                    f"{n.icon!r} is a group container, not a node icon",
                    pointer=ptr,
                    fix="use a service icon; group containers for zones are planned",
                )
            )
            continue
        if n.tag:
            out.append(
                Finding(
                    "SPEC-032",
                    f"node {n.id!r} has both a tag and an icon; the tag is not drawn",
                    pointer=f"{base}/{n.index}/tag",
                    severity="warn",
                    fix="drop the tag; the icon already says what kind of service it is",
                )
            )
        by_platform.setdefault(fams[entry.family].platform, set()).add(entry.family)
        used_families.add(entry.family)
    for platform, fs in sorted(by_platform.items()):
        if len(fs) > 1:
            out.append(
                Finding(
                    "LR-I002",
                    f"{platform} icons mix families {', '.join(sorted(fs))}; their styles clash",
                    pointer=base,
                    severity="warn",
                    fix="use one family per platform (`ddraw icons search --family <one>`)",
                )
            )
    if spec.icon_style == "mono":
        fixed = sorted(f for f in used_families if fams[f].recolor == "none")
        if fixed:
            out.append(
                Finding(
                    "LR-I004",
                    f"iconStyle mono cannot recolour {', '.join(fixed)}; those icons keep vendor colours",
                    pointer="/iconStyle",
                    severity="warn",
                    fix="use iconStyle vendor, or icons from a recolourable family (aws4, kubernetes)",
                )
            )
    comparable = [n for n in spec.nodes if n.role not in ICON_EXEMPT_ROLES]
    bare = [n.id for n in comparable if not n.icon]
    if bare and any(n.icon for n in comparable):
        out.append(
            Finding(
                "LR-I005",
                f"some services have icons and some do not ({', '.join(bare)})",
                pointer=base,
                severity="warn",
                fix="give every service an icon or none (externals, clients and actors are exempt)",
            )
        )
    return out


def _sequence_checks(spec: Spec, info: registry.TypeInfo) -> list[Finding]:
    out: list[Finding] = []
    seq = spec.raw.get("sequence")
    if not isinstance(seq, dict):
        return [
            Finding(
                "SPEC-030",
                'sequence diagrams need a "sequence" block with participants and messages',
                pointer="/sequence",
                fix="see references/type-sequence.md",
            )
        ]
    if spec.raw.get("nodes") or spec.raw.get("edges"):
        out.append(
            Finding(
                "SPEC-031",
                "use sequence.participants and sequence.messages, not nodes/edges",
                pointer="/nodes",
            )
        )
    budget = registry.type_budget(spec.type, spec.detail)
    if len(spec.nodes) > budget.get("lifelines", 5):
        out.append(
            Finding(
                "LR-B005",
                f"{len(spec.nodes)} lifelines; at most {budget.get('lifelines', 5)}",
                pointer="/sequence/participants",
                fix="merge participants or split the flow",
            )
        )
    n_msgs = len(spec.edges)
    frags = seq.get("fragments", [])
    if len(frags) > budget.get("fragments", 2):
        out.append(
            Finding(
                "LR-B005",
                f"{len(frags)} fragments; at most {budget.get('fragments', 2)}",
                pointer="/sequence/fragments",
            )
        )
    spans: list[tuple[int, int]] = []
    for i, f in enumerate(frags):
        lo, hi = int(f["from"]), int(f["to"])
        if not 1 <= lo <= hi <= n_msgs:
            out.append(
                Finding(
                    "SPEC-032",
                    f"fragment covers messages {lo}–{hi}; messages are numbered 1–{n_msgs}",
                    pointer=f"/sequence/fragments/{i}",
                )
            )
        if "elseAt" in f and not lo < int(f["elseAt"]) <= hi:
            out.append(
                Finding(
                    "SPEC-033",
                    "elseAt must fall inside the fragment, after its first message",
                    pointer=f"/sequence/fragments/{i}/elseAt",
                )
            )
        if "elseAt" in f and f["kind"] != "alt":
            out.append(
                Finding(
                    "SPEC-033",
                    "only alt fragments have an else region",
                    pointer=f"/sequence/fragments/{i}/elseAt",
                )
            )
        for a, b in spans:
            overlap = not (hi < a or lo > b)
            nested = (a <= lo and hi <= b) or (lo <= a and b <= hi)
            if overlap and not nested:
                out.append(
                    Finding(
                        "SPEC-034", "fragments must nest or be disjoint", pointer=f"/sequence/fragments/{i}"
                    )
                )
        spans.append((lo, hi))
    return out


def _tree_checks(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    budget = registry.type_budget(spec.type, spec.detail)
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {}
    for e in spec.edges:
        parents.setdefault(e.dst, []).append(e.src)
        children.setdefault(e.src, []).append(e.dst)
    for i, n in enumerate(spec.nodes):
        if len(parents.get(n.id, [])) > 1:
            out.append(
                Finding(
                    "LR-Y-tree-001",
                    f"{n.id!r} has {len(parents[n.id])} parents; a tree has one",
                    pointer=f"/nodes/{i}",
                    fix="use an architecture or dependency diagram for fan-in",
                )
            )
        if len(children.get(n.id, [])) > budget.get("breadth", 5):
            out.append(
                Finding(
                    "LR-Y-tree-002",
                    f"{n.id!r} has {len(children[n.id])} children; at most {budget.get('breadth', 5)}",
                    pointer=f"/nodes/{i}",
                    fix="group children under intermediate nodes (pods, teams)",
                )
            )
    roots = [n.id for n in spec.nodes if n.id not in parents]
    if not roots and spec.nodes:
        out.append(Finding("LR-Y-tree-003", "no root: every node has a parent (cycle)", pointer="/edges"))
    depth: dict[str, int] = {}

    def walk(node: str, d: int, seen: frozenset[str]) -> None:
        if node in seen:
            return
        depth[node] = max(depth.get(node, 0), d)
        for c in children.get(node, []):
            walk(c, d + 1, seen | {node})

    for r in roots:
        walk(r, 1, frozenset())
    deepest = max(depth.values(), default=0)
    if deepest > budget.get("depth", 4):
        out.append(
            Finding(
                "LR-Y-tree-004",
                f"tree is {deepest} levels deep; at most {budget.get('depth', 4)}",
                pointer="/nodes",
                fix="collapse a level or split into overview + subtree",
            )
        )
    return out


def load_spec(path: Path) -> tuple[Spec, list[Finding]]:
    data = load_json(path)
    spec, findings = validate(data)
    if spec is None:
        raise DDError(findings)
    return spec, findings
