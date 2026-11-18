---
description: Lint a draw.io diagram against draw-design's editorial and structural rules
argument-hint: "<file.drawio> [--strict] [--rules LR-C,LR-G001]"
allowed-tools: [Bash, Read]
---

Lint the named diagram with `<skill-dir>/bin/ddraw lint $ARGUMENTS --json` (`<skill-dir>` is this plugin's `skills/draw-design`, the folder holding the draw-design `SKILL.md`). `skills/draw-design/references/lint.md` explains every rule.

Full argument string: `$ARGUMENTS`. If the host left that as an unfilled placeholder, use the text the user typed after the command instead.

1. No file given: ask which `.drawio` file.
2. Summarise the findings grouped by rule, most severe first, each with its fix. Files not built by draw-design report metadata-dependent rules as `info`; say so once.
3. If the diagram has a sibling `.dd.json` spec, offer to fix the spec and rebuild. Otherwise offer concrete manual edits. Do not modify files unless the user asks.
