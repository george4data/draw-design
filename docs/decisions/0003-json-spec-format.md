# ADR 0003: The spec format is JSON; YAML is optional

**Status:** accepted (2026-11-17)

## Context

YAML is friendlier for humans but needs PyYAML, which is not in the standard library.

## Decision

Canonical spec files are JSON (`.dd.json`). YAML input is accepted only when PyYAML is importable.

## Consequences

Agents write JSON reliably. Error pointers use JSON Pointer syntax.
