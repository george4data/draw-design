# ADR 0001: Spec-first: the LLM writes a Diagram Spec; a deterministic compiler emits draw.io XML

**Status:** accepted (2026-11-17)

## Context

LLM-written mxGraph XML fails in predictable ways: duplicate ids, missing parents, unescaped HTML labels, diagonal and overlapping edges, off-grid geometry and palette drift.

## Decision

The runtime agent authors a compact JSON Diagram Spec (`*.dd.json`). The `ddraw` toolchain validates it, binds the theme, lays it out, routes connectors, emits `.drawio` XML and lints the result.

## Consequences

Output is deterministic and testable. Re-theming is a recompile. The skill text holds judgement; Python holds mechanics. Hand-written XML is never used for output (FR-018).
