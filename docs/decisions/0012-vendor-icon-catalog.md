# ADR 0012: Vendor icon catalog from the drawio-mcp index, verified by rendering

**Status:** accepted (2026-11-17), verified against draw.io Desktop 32.7.4. Refines PRD §10.8 (T-2.11, T-2.12).

## Context

The PRD planned to build the catalog by parsing draw.io's sidebar JavaScript at a pinned tag, with a per-family `since` version. Investigating the installed draw.io Desktop turned up four things:

- **The sidebar code is minified and builds styles from local variables.** Parsing it is brittle.
- **jgraph publishes `shape-search/search-index.json` in `jgraph/drawio-mcp`** (Apache-2.0). It is generated from the same sidebar code by running it, and it is regenerated daily. It has 10,800 entries with exact styles.
- **The index runs ahead of any given Desktop release, and some entries don't draw.** We rendered 2,558 vendor entries with Desktop 32.7.4 in one 4-second export:

  | Family | Drew | Notes |
  |---|---|---|
  | `aws4` | 1,354 / 1,355 | |
  | `gcp3` | 45 / 45 | |
  | GCP product icons | 266 / 266 | inline SVG |
  | `gcp2` | 110 / 113 | |
  | Kubernetes | 78 / 78 | |
  | Azure | all but 4 | images; the 4 that failed are probably newer than 32.7.4 |

  Unknown names are easy to detect in an SVG export. An unknown `shape=` falls back to a `<rect>`, and an unknown AWS `resIcon` draws only its background tile.
- **Azure icons are `img/lib/azure2/*.svg` paths inside the app bundle.** A plain SVG export links them as `file:///Applications/draw.io.app/...`, which breaks on any other machine. `--embed-svg-images` inlines them.

## Decision

- **Source and verification.** `scripts/build-shape-catalog.py` (run with `make shapes`) reads the drawio-mcp index at a pinned commit and classifies entries into families: `aws4`, `gcp` (the current Google Cloud product icons), `gcp3`, `gcp2` (legacy), `azure2` and `kubernetes`.
  - Duplicates are resolved deterministically: coloured tiles beat white tiles, and light group variants beat dark ones.
  - It renders every entry with draw.io Desktop and drops what doesn't draw.
  - It records `verifiedWith` in place of a per-family `since`.
  - The output is about 170 KB gzipped, and a rebuild reproduces it byte for byte.
- **Search.** Search ranks by title, name and tag overlap, plus a short curated alias list (postgres → RDS, Aurora, Cloud SQL; redis → ElastiCache, Memorystore; and so on).
- **Recolouring.** Monochrome support was decided per family by test renders. `aws4` and `kubernetes` recolour through `fillColor`. `gcp3` and `gcp2` recolour only partly, and the image families can't recolour, so all four are marked `recolor: none`.
- **Placement.** Icons are drawn **inside** editorial nodes: 28 px, 12 px from the left edge, with the label left-aligned after a 10 px gap. Nodes gain 30 px of width. The icon replaces the node's tag chip. Icons are allowed on `architecture` and `sequence`.
  - **Standalone** placement (the icon as the node, label below) is deferred. A prototype showed that it needs layout support for the icon-plus-label footprint and for ports on the icon.
- **Export.** SVG export always passes `--embed-svg-images`.
- **Version checks.** The doctor warns when the installed draw.io is older than `verifiedWith`. LR-I003 (per-shape version drift) is not built.

## Consequences

- Agents can use about 2,000 verified vendor icons offline. The build rejects unknown ids with did-you-mean suggestions (LR-I001).
- Catalog updates are a reviewable data diff produced by `make shapes`.
- Vendor group containers for zones (T-3.25), standalone placement, generic bundled icons and icon-pack import (T-4.28) remain open.
