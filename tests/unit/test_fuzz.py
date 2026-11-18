"""Seeded property test: random in-budget architecture graphs build without connector violations."""

from __future__ import annotations

import random
from typing import Any

import pytest

from ddraw.errors import DDError
from ddraw.pipeline import build

SEEDS = range(120)
ROLES = ["backend", "backend", "store", "external", "input"]


def random_spec(seed: int) -> dict[str, Any]:
    rnd = random.Random(seed)
    n = rnd.randint(2, 9)
    nodes: list[dict[str, Any]] = []
    for i in range(n):
        node: dict[str, Any] = {"id": f"n{i}", "label": f"Service {i}", "role": rnd.choice(ROLES)}
        if rnd.random() < 0.5:
            node["sublabel"] = f"svc-{i}:{8000 + i}"
        nodes.append(node)
    edges: list[dict[str, Any]] = []
    pairs: set[tuple[int, int]] = set()
    for _ in range(rnd.randint(n - 1, min(12, 2 * n))):
        a, b = rnd.sample(range(n), 2)
        if (a, b) in pairs or (b, a) in pairs:
            continue
        pairs.add((a, b))
        edge: dict[str, Any] = {"from": f"n{a}", "to": f"n{b}"}
        if rnd.random() < 0.3:
            edge["label"] = rnd.choice(["SQL", "HTTPS", "GRPC", "EVENTS"])
        edges.append(edge)
    nodes[rnd.randrange(n)]["focal"] = True
    return {
        "ddVersion": 1,
        "type": "architecture",
        "title": f"Fuzz {seed}",
        "description": "Randomly generated architecture used to test routing invariants.",
        "size": rnd.choice(["doc-inline", "doc-wide", "fit"]),
        "direction": rnd.choice(["LR", "TB"]),
        "nodes": nodes,
        "edges": edges,
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_random_graph(seed: int) -> None:
    spec = random_spec(seed)
    try:
        result = build(spec)
    except DDError as exc:
        codes = {f.code for f in exc.findings}
        # Capacity and label-room failures are legitimate "split or resize" answers, not bugs.
        assert codes <= {"LAYOUT-001", "ROUTE-002"}, [f.human() for f in exc.findings]
        return
    bad = [f.human() for f in result.findings if f.severity == "error"]
    assert bad == [], spec
