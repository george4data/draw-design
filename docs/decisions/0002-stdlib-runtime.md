# ADR 0002: The runtime is Python standard library only; draw.io Desktop is optional

**Status:** accepted (2026-11-17)

## Context

Hosts install skills by copying a folder. Third-party dependencies would need an installer step the host does not provide.

## Decision

`ddraw` uses only the Python ≥3.10 standard library. The draw.io Desktop CLI is used only for export and preview, detected at runtime.

## Consequences

No layout libraries (Graphviz, ELK) at runtime; layout engines are implemented in-house. Dev tools (pytest, ruff, mypy) are dev-only.
