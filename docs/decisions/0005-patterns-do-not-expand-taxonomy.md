# ADR 0005: Semantic patterns never expand the visual-type taxonomy

**Status:** accepted (2026-11-17)

## Context

Ported from diagram-design ADR 0002. Behaviour (queues, policy traces, trust boundaries) is a different axis from layout.

## Decision

A semantic pattern routes to its nearest visual type and owns only required primitives and a tighter budget.

## Consequences

The type count grows only for genuinely new layout grammars.
