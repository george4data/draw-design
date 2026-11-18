---
description: Export a draw.io diagram to PNG, SVG, PDF or an editable .drawio.png / .drawio.svg
argument-hint: "<file.drawio> [--format png|svg|pdf|drawio.png|drawio.svg] [--scale N] [--page N] [--theme light|dark] [-o path]"
allowed-tools: [Bash, Read]
---

Export the diagram named in the arguments, following `skills/draw-design/references/export.md` (the source of truth).

Full argument string: `$ARGUMENTS`

## Defaults

`--format png`, `--scale 2`, transparent background, output next to the source without overwriting.

## Required behaviour

1. No file given: ask which `.drawio` file. Don't guess.
2. Run `<skill-dir>/bin/ddraw export $ARGUMENTS` from the user's project directory (`<skill-dir>` is this plugin's `skills/draw-design`).
3. Exit code 3 means draw.io Desktop is missing: relay the install hint and suggest `/draw-design:doctor`.
4. Report the written path. If the doctor would warn about missing fonts, mention that the export used fallback fonts.
