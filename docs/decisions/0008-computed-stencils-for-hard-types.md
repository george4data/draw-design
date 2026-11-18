# ADR 0008: Filled-curve types use computed inline stencils

**Status:** accepted (2026-11-17)

## Context

draw.io cannot fill an arbitrary path natively; sankey ribbons, radar fills and axonometric faces need filled curves.

## Decision

Use per-cell `shape=stencil(<compressed stencil>)` with path operations. Embedded images are a last resort.

## Consequences

Shapes stay movable and theme-coloured. Stencil work is isolated in milestone M5.
