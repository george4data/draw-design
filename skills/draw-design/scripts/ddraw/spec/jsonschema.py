"""A small JSON Schema (draft 2020-12 subset) validator, standard library only.

Supports: type, enum, const, pattern, required, properties, additionalProperties
(bool or schema), items, minItems/maxItems, minLength/maxLength, minimum/maximum,
maxProperties and local `$ref` (`#/$defs/...`). That is everything our schemas use.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from ddraw.errors import Finding

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _is_type(value: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    py = _TYPES[t]
    if py is bool:
        return isinstance(value, bool)
    if py in (int, float):
        return isinstance(value, py) and not isinstance(value, bool)
    return isinstance(value, py)


def _esc(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


class Validator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.root = schema

    def _resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"only local refs are supported: {ref}")
        node: Any = self.root
        for part in ref[2:].split("/"):
            node = node[part]
        return dict(node)

    def validate(self, value: Any) -> list[Finding]:
        out: list[Finding] = []
        self._check(value, self.root, "", out)
        return out

    def _check(self, v: Any, s: dict[str, Any], ptr: str, out: list[Finding]) -> None:
        if "$ref" in s:
            s = self._resolve(s["$ref"])
        where = ptr or "/"
        if "const" in s and v != s["const"]:
            out.append(Finding("SPEC-003", f"must be {s['const']!r}", pointer=where))
            return
        t = s.get("type")
        if t is not None:
            types = t if isinstance(t, list) else [t]
            if not any(_is_type(v, x) for x in types):
                out.append(
                    Finding(
                        "SPEC-004", f"expected {' or '.join(types)}, got {type(v).__name__}", pointer=where
                    )
                )
                return
        if "enum" in s and v not in s["enum"]:
            options = ", ".join(repr(x) for x in s["enum"])
            close = difflib.get_close_matches(str(v), [str(x) for x in s["enum"]], n=1)
            fix = f"did you mean {close[0]!r}?" if close else f"one of: {options}"
            out.append(Finding("SPEC-005", f"{v!r} is not allowed", pointer=where, fix=fix))
        if isinstance(v, str):
            if "minLength" in s and len(v) < s["minLength"]:
                out.append(Finding("SPEC-006", f"shorter than {s['minLength']} characters", pointer=where))
            if "maxLength" in s and len(v) > s["maxLength"]:
                out.append(
                    Finding(
                        "SPEC-006",
                        f"longer than {s['maxLength']} characters ({len(v)})",
                        pointer=where,
                        fix="shorten it; cut words rather than shrinking type",
                    )
                )
            if "pattern" in s and not re.search(s["pattern"], v):
                out.append(Finding("SPEC-007", f"{v!r} does not match {s['pattern']}", pointer=where))
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if "minimum" in s and v < s["minimum"]:
                out.append(Finding("SPEC-008", f"must be ≥ {s['minimum']}", pointer=where))
            if "maximum" in s and v > s["maximum"]:
                out.append(Finding("SPEC-008", f"must be ≤ {s['maximum']}", pointer=where))
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                out.append(Finding("SPEC-009", f"needs at least {s['minItems']} items", pointer=where))
            if "maxItems" in s and len(v) > s["maxItems"]:
                out.append(Finding("SPEC-009", f"at most {s['maxItems']} items", pointer=where))
            if "items" in s:
                for i, item in enumerate(v):
                    self._check(item, s["items"], f"{ptr}/{i}", out)
        if isinstance(v, dict):
            for req in s.get("required", []):
                if req not in v:
                    out.append(Finding("SPEC-001", f"missing required key {req!r}", pointer=where))
            props: dict[str, Any] = s.get("properties", {})
            addl = s.get("additionalProperties", True)
            if "maxProperties" in s and len(v) > s["maxProperties"]:
                out.append(Finding("SPEC-009", f"at most {s['maxProperties']} keys", pointer=where))
            for key, item in v.items():
                sub = f"{ptr}/{_esc(key)}"
                if key in props:
                    self._check(item, props[key], sub, out)
                elif addl is False:
                    close = difflib.get_close_matches(key, list(props), n=1)
                    out.append(
                        Finding(
                            "SPEC-002",
                            f"unknown key {key!r}",
                            pointer=sub,
                            fix=f"did you mean {close[0]!r}?" if close else "remove it",
                        )
                    )
                elif isinstance(addl, dict):
                    self._check(item, addl, sub, out)
