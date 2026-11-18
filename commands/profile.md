---
description: Create, list, show, select or delete draw-design brand profiles (client themes)
argument-hint: "<list|new|show|use|load|reset|delete> [slug] [--name ...] [--source theme.json]"
allowed-tools: [Bash, Read, Edit]
---

Manage brand profiles following `skills/draw-design/references/profiles.md` (the source of truth).

Full argument string: `$ARGUMENTS`

1. Run `<skill-dir>/bin/ddraw profile $ARGUMENTS` (`<skill-dir>` is this plugin's `skills/draw-design`).
2. `new` with an existing slug fails: ask the user before retrying with `--force`. `delete` needs explicit confirmation, then `--yes`.
3. After `new`, offer to set the brand colours (reference §"Making a brand profile"), run `ddraw theme check`, and `use` it for the current project.
