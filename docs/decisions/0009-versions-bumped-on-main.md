# ADR 0009: Versions are bumped on main after merge

**Status:** accepted (2026-11-17)

## Context

Ported from diagram-design ADR 0009. Bumping in PRs makes every open PR conflict on manifest version lines.

## Decision

PRs never change manifest versions. A script on `main` bumps all manifests together.

## Consequences

Manifest versions stay synchronized and PRs stay mergeable.
