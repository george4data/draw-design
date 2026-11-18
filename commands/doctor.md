---
description: Check that draw-design can build, lint and export diagrams on this machine
argument-hint: "[--strict] [--json]"
allowed-tools: [Bash, Read]
---

Run the draw-design environment doctor, following `skills/draw-design/references/doctor.md` (the source of truth).

Full argument string: `$ARGUMENTS`

1. Locate the installed skill directory (the folder containing `skills/draw-design/SKILL.md` of this plugin). Do not assume it is under the current working directory.
2. Run `<skill-dir>/bin/ddraw doctor $ARGUMENTS`.
3. Print the summary and every check line. If anything warns or fails, list the `Next actions` exactly. Do not install anything or change any file.
