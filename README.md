# draw-design

Editorial, on-brand diagrams as **native, editable draw.io files**, for Claude Code and Codex.

You describe a system, a process or a flow. The agent picks the diagram type and writes a compact **Diagram Spec** (`*.dd.json`). The bundled `ddraw` compiler then:

- lays the diagram out on a 4px grid;
- routes right-angle connectors that never overlap or pass behind boxes;
- applies your brand theme;
- lints the result against editorial rules;
- writes a `.drawio` file you can keep editing in draw.io Desktop, diagrams.net or the VS Code draw.io extension.

PNG, SVG and PDF exports go through the draw.io Desktop command line.

| | |
|---|---|
| ![Architecture](gallery/png/architecture.png) | ![Sequence](gallery/png/sequence.png) |
| ![Flowchart](gallery/png/flowchart.png) | ![Swimlane](gallery/png/swimlane.png) |
| ![State machine](gallery/png/state.png) | ![Org chart](gallery/png/org-chart.png) |
| ![AWS architecture with vendor icons](gallery/png/architecture-aws.png) | |

> Status: early development (v0.1). See [`docs/prd.md`](docs/prd.md) for the full spec and roadmap, and its §22.10 for what is implemented.

## What it does today

| Capability | Command |
|---|---|
| 8 diagram types: architecture, flowchart, sequence, swimlane, state machine, tree, org chart, layer stack | `ddraw build spec.dd.json` |
| Official AWS, Google Cloud, Azure and Kubernetes icons (about 2,000, verified to render in draw.io, offline), in vendor colours or monochrome | `ddraw icons search "sqs queue" --platform aws`, then `"icon": "aws4:sqs"` |
| Validated spec with JSON-pointer errors and "did you mean" fixes | `ddraw validate`, `ddraw new <type>` |
| Editorial lint of any draw.io file (structure, 4px grid, budgets, connector rules, palette, fonts, legend, unsafe links) | `ddraw lint file.drawio` |
| Export PNG / SVG / PDF / editable `.drawio.png` / `.drawio.svg`, with accessible SVG titles | `ddraw export file.drawio --format png` |
| Brand profiles per client, selected per project by a `.draw-design` marker | `ddraw profile new/use/list/show` |
| Restyle an existing draw.io file to the theme, keeping its layout | `ddraw import legacy.drawio --snap` |
| Environment check | `ddraw doctor` |

## Install

**Claude Code**

```text
/plugin marketplace add <owner>/draw-design
/plugin install draw-design@draw-design
```

**Codex**

```bash
codex plugin marketplace add <owner>/draw-design
codex plugin add draw-design@draw-design
```

**Standalone skill** (any Agent Skills host): symlink `skills/draw-design` into your host's skills folder, e.g. `~/.claude/skills/draw-design`.

Requirements: Python ≥ 3.10 (standard library only). Optional: [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) for export and preview. For faithful exports, also install the theme fonts: Instrument Serif, Geist and Geist Mono (all SIL OFL).

```bash
skills/draw-design/bin/ddraw doctor
```

## Quick start (CLI)

```bash
DD=skills/draw-design/bin/ddraw
$DD types                               # shipped diagram types
$DD new architecture -o app.dd.json     # scaffold a spec
$DD build app.dd.json                   # → app.drawio (only written when lint is clean)
$DD export app.drawio --format png      # → app.png (2×, transparent)
```

In Claude Code or Codex, just ask: *"draw the architecture of this repo as a draw.io diagram"*. The skill writes the spec, builds, checks the rendered preview, and hands you the `.drawio` file.

## How it relates to the official draw.io plugin

jgraph publishes an official draw.io skill that authors Mermaid or raw XML. draw-design is complementary. It focuses on:

- **editorial quality:** density budgets, one focal accent, connector rules, type-specific layouts;
- **brand theming:** client profiles selected per project;
- **restyling** existing diagrams to a house style.

## Development

```bash
make venv     # .venv with pytest, ruff, mypy (via uv)
make check    # ruff + mypy --strict + pytest + docs/package checks
make render   # rebuild gallery/ and render PNGs (needs draw.io Desktop)
```

Read [AGENTS.md](AGENTS.md) first. Architecture decisions are recorded in [`docs/decisions/`](docs/decisions/).

## License

MIT. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for attributions (design rules adapted from [diagram-design](https://github.com/cathrynlavery/diagram-design), MIT).
