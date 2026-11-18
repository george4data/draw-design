# ADR 0006: Client profiles use marker-first resolution

**Status:** accepted (2026-11-17)

## Context

Ported from diagram-design ADR 0006. A shared installed theme supports one client only and is lost on updates.

## Decision

Profiles live in `~/.draw-design/profiles/<slug>.json`. A project `.draw-design` file containing exactly `profile: <slug>` selects one and is read directly, without touching the installed theme.

## Consequences

Parallel workspaces for different clients are safe.
