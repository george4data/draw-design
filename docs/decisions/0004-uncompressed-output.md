# ADR 0004: Output is uncompressed XML

**Status:** accepted (2026-11-17)

## Context

draw.io saves compressed diagrams by default, which makes diffs and reviews impossible.

## Decision

`ddraw` writes `compressed="false"` XML with stable attribute order. Compressed input is still decoded.

## Consequences

Files are larger but diffable and deterministic.
