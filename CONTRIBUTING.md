# Contributing

- Read [AGENTS.md](AGENTS.md) and [docs/prd.md](docs/prd.md) §0 and §21.
- `make venv && make check` must pass before you open a PR.
- One task (PRD §22) per PR. Name the task id and the FR/LR ids it implements.
- Golden-file changes need a one-line justification in the PR description.
- Don't change manifest versions. Versions are bumped on `main` after merge (ADR 0009).
