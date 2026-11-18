# ADR 0007: Per-type registration files enable parallel agent work

**Status:** accepted (2026-11-17)

## Context

Shared registries (types table, budgets, SKILL.md selection table) cause merge conflicts when agents add types in parallel.

## Decision

Each type owns `data/types.d/<slug>.json` (registry + budget). Shared tables are generated from these files.

## Consequences

Adding a type never edits a shared file by hand.
