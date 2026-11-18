from __future__ import annotations

import copy
from typing import Any

import pytest

from ddraw.spec.validate import validate
from helpers import example


def codes(data: dict[str, Any]) -> list[tuple[str, str]]:
    _, findings = validate(data)
    return [(f.code, f.pointer or "") for f in findings if f.severity == "error"]


def test_examples_are_valid() -> None:
    for name in ("architecture", "flowchart"):
        spec, findings = validate(example(name))
        assert spec is not None, [f.human() for f in findings]


def mutate(fn: Any) -> dict[str, Any]:
    d = copy.deepcopy(example("architecture"))
    fn(d)
    return d


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda d: d.pop("title"), ("SPEC-001", "/")),
        (lambda d: d.update(colour="red"), ("SPEC-002", "/colour")),
        (lambda d: d["nodes"][0].update(lable="x"), ("SPEC-002", "/nodes/0/lable")),
        (lambda d: d.update(size="poster"), ("SPEC-005", "/size")),
        (lambda d: d.update(ddVersion=2), ("SPEC-003", "/ddVersion")),
        (lambda d: d["nodes"][0].update(label="x" * 33), ("SPEC-006", "/nodes/0/label")),
        (lambda d: d["nodes"][0].update(id="Bad Id"), ("SPEC-007", "/nodes/0/id")),
        (lambda d: d["edges"][0].update(label="A VERY LONG LABEL"), ("LR-C007", "/edges/0/label")),
        (lambda d: d.update(type="sequencee"), ("SPEC-010", "/type")),
        (lambda d: d.update(type="sankey"), ("SPEC-011", "/type")),
        (lambda d: d["nodes"][1].update(id="web"), ("SPEC-020", "/nodes/1/id")),
        (lambda d: d["nodes"][0].update(role="database"), ("SPEC-021", "/nodes/0/role")),
        (lambda d: d["nodes"][0].update(zone="nowhere"), ("SPEC-022", "/nodes/0/zone")),
        (lambda d: d["edges"][0].update(to="ghost"), ("SPEC-023", "/edges/0/to")),
        (lambda d: d["nodes"][1].update(focal=True), ("LR-B003", "/nodes")),
    ],
)
def test_invalid_specs_point_at_the_problem(mutation: Any, expected: tuple[str, str]) -> None:
    assert expected in codes(mutate(mutation))


def test_did_you_mean_for_enum_and_keys() -> None:
    _, findings = validate(mutate(lambda d: d.update(size="doc-inlne")))
    assert any(f.fix == "did you mean 'doc-inline'?" for f in findings)
    _, findings = validate(mutate(lambda d: d["nodes"][0].update(sublable="x")))
    assert any(f.fix == "did you mean 'sublabel'?" for f in findings)


def test_node_budget() -> None:
    def many(d: dict[str, Any]) -> None:
        d["nodes"] += [{"id": f"n{i}", "label": f"N{i}"} for i in range(5)]

    assert ("LR-B001", "/nodes") in codes(mutate(many))


def test_flowchart_decision_exits_must_be_labelled() -> None:
    d = copy.deepcopy(example("flowchart"))
    d["edges"][1].pop("label")
    assert ("LR-Y-flowchart-002", "/edges/1/label") in codes(d)


def test_sequence_alt_fragment_builds_and_validates() -> None:
    from ddraw.pipeline import build

    d = example("sequence")
    seq = d["sequence"]
    seq["fragments"] = [
        {"kind": "alt", "label": "cached", "from": 5, "to": 8, "elseAt": 7, "elseLabel": "expired"}
    ]
    d["size"] = "fit"
    result = build(d)
    assert result.ok, [f.human() for f in result.findings]
    assert 'dd-role="else"' in result.xml and "[expired]" in result.xml


@pytest.mark.parametrize(
    ("fragment", "code"),
    [
        ({"kind": "opt", "from": 3, "to": 99}, "SPEC-032"),
        ({"kind": "opt", "from": 3, "to": 5, "elseAt": 4}, "SPEC-033"),
        ({"kind": "alt", "from": 3, "to": 5, "elseAt": 3}, "SPEC-033"),
    ],
)
def test_sequence_fragment_errors(fragment: dict[str, Any], code: str) -> None:
    d = example("sequence")
    d["sequence"]["fragments"] = [fragment]
    assert code in {c for c, _ in codes(d)}


def test_sequence_needs_its_block() -> None:
    d = example("sequence")
    d.pop("sequence")
    d["nodes"] = [{"id": "a", "label": "A"}]
    assert "SPEC-030" in {c for c, _ in codes(d)}
