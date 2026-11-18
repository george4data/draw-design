# Doctor

`<skill-dir>/bin/ddraw doctor [--strict] [--json] [--project <root>]` is a read-only environment check. It installs nothing and edits nothing.

Checks, in order: Python ≥ 3.10 · skill files present · type registry loads · draw.io Desktop CLI found (warn if missing: export and preview unavailable) · headless display on Linux (xvfb) · theme fonts installed locally (warn: exports substitute fallbacks) · profile library writable · project `.draw-design` marker valid · default theme contrast.

Output: `Doctor summary: PASS|WARN|FAIL (n pass, n warn, n fail)`, one `[STATUS]` line per check, then `Next actions` when anything is not passing. `--json` appends `{status, counts, checks[], timestamp}`. Report only what this run verified; give the user the copy-pastable fixes from `Next actions`.

draw.io Desktop locations searched: `$DRAWIO_CLI`, `drawio` / `draw.io` on PATH, `/Applications/draw.io.app/Contents/MacOS/draw.io`, `~/Applications/…`, `/opt/drawio/drawio`, `/snap/bin/drawio`, `%ProgramFiles%\draw.io\draw.io.exe`, `%LOCALAPPDATA%\Programs\draw.io\draw.io.exe`.
