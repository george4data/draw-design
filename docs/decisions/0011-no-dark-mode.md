# ADR 0011: No dark mode

**Status:** accepted (2026-11-17). Supersedes items 4–5 of [ADR 0010](0010-drawio-rendering-facts.md) and resolves OQ-04 differently.

## Context

v0.1 shipped two colour skins. The normal file stored every colour as `light-dark(light,dark)`, and `variant: dark` produced a fixed dark rendering. Reviewing the dark renders showed that the colours did not look right. draw.io also has interactions that are easy to get wrong:

- `--theme dark` inverts plain hex;
- inline HTML colours are not adapted;
- a dark-mode app shows `light-dark()` files in their dark skin whether or not the author meant it.

Every theme and client profile had to carry and contrast-check a second palette.

## Decision

Diagrams have **one light palette**.

- Themes and profiles hold a single `colors` table. The loader still accepts the old `light` + `dark` layout, keeps `light` as `colors` and ignores `dark`, so profiles created with v0.1 keep working.
- The emitter writes plain opaque hex and keeps `adaptiveColors="none"` on `mxGraphModel`. draw.io's dark UI therefore shows the diagram exactly as drawn.
- `ddraw export` always passes `--theme light`; there is no `--theme` option. `ddraw build --no-adaptive` is removed.
- The spec's `variant` no longer accepts `light`, `dark` or `both`.
- The gallery has no `-dark` files.
- Lint still parses `light-dark()` in foreign files and checks both halves against the palette.

## Consequences

The theme surface, the contrast check and the gallery all shrink by half. The style guide is simpler.

A dark diagram could in principle be made as a profile with dark `paper`, light `ink` and a dark `nodeFill`. That route is untested; the contrast check would still apply.

Adding real dark mode later needs a new ADR, plus visual QA of every type in draw.io's dark UI and in exports.
