# draw-design

Editorial, on-brand diagrams as **native, editable draw.io files**, for Claude Code and Codex.

You describe a system, a process or some data. The agent picks the right diagram type, writes a compact Diagram Spec, and the `ddraw` compiler lays it out on a 4px grid, routes orthogonal connectors, applies your brand theme, lints the result against editorial rules, and writes a `.drawio` file you can keep editing in draw.io Desktop, diagrams.net or the VS Code draw.io extension. PNG, SVG and PDF exports go through the draw.io Desktop CLI.

> Status: early development. See [`docs/prd.md`](docs/prd.md) for the full product spec and roadmap.

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

Optional: install [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) for PNG/SVG/PDF export and visual preview. Run the doctor to check your setup:

```bash
skills/draw-design/scripts/ddraw doctor
```

## Quick start (CLI)

```bash
skills/draw-design/scripts/ddraw types                       # list diagram types
skills/draw-design/scripts/ddraw new architecture -o app.dd.json
skills/draw-design/scripts/ddraw build app.dd.json -o app.drawio
skills/draw-design/scripts/ddraw lint app.drawio
skills/draw-design/scripts/ddraw export app.drawio --format png
```

## How it relates to the official draw.io plugin

jgraph publishes an official draw.io skill that authors Mermaid or raw XML. draw-design is complementary: it focuses on editorial quality (density budgets, one focal accent, orthogonal connector rules), brand theming with client profiles, and restyling or redrawing existing diagrams.

## License

MIT. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for attributions.
