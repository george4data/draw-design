# ADR 0010: draw.io rendering behaviour the emitter relies on

**Status:** accepted (2026-11-17), verified against draw.io Desktop 32.7.4

## Context

The PRD left several draw.io behaviours to verify (OQ-04, §10.3, §B.1). The compiler's output only looks right if these hold.

## Decision

Verified by exporting prototype files with the desktop CLI and inspecting the SVG/PNG output:

1. **Explicit waypoints survive `edgeStyle=orthogonalEdgeStyle`.** draw.io draws exactly our port → waypoints → port polyline, and keeps it orthogonal when a user later drags a node. The emitter uses `orthogonalEdgeStyle` + `exitX/exitY/entryX/entryY` + `<Array as="points">`.
2. **Edge corner radius with `rounded=1` is 10px** (the reference's 8px is not configurable per edge). Accepted.
3. **Edge label position:** geometry `x` maps linearly to `(x+1)/2` of the total polyline length, then `<mxPoint as="offset">` shifts it in px. The router computes both, so labels sit 8px off the stroke.
4. **`light-dark(a,b)` works** in style colours and the model `background`. A file with `light-dark()` colours renders the light skin by default and the dark skin with `--theme dark` (and in draw.io's dark mode).
5. **`--theme dark` inverts plain hex colours** even with `adaptiveColors="none"`. Therefore:
   - `variant: light` (default) emits `light-dark(light,dark)` pairs, so the file follows the viewer's mode.
   - `variant: dark` emits plain dark-skin hex: a fixed dark rendering. Export it **without** `--theme dark`.
6. **Inline HTML colours inside labels are not adapted.** Sublabels therefore inherit the cell's adaptive `fontColor` and use `opacity:0.78` instead of their own colour.
7. A frame cell with `strokeWidth=0` still widens PNG export by about 1px per side. Exported pixel sizes are frame × scale ± 2px.

## Consequences

OQ-04 is resolved. Export documentation tells agents not to combine `variant: dark` with `--theme dark`.
