# Lint rules

`ddraw lint <file.drawio> [--json] [--strict] [--rules LR-C,LR-G001]` checks any draw.io file. Files built by `ddraw` carry `dd-*` metadata and get every rule. For other files, rules that need that metadata report as `info` only.

| Rule | Checks |
|---|---|
| LR-S001–S007 | well-formed file, unique ids, existing parents and edge endpoints, finite geometry, no scripts or event handlers in labels, title and description present, uncompressed XML (S006 warn) |
| LR-G001 | boxes on the 4px grid |
| LR-G003 | everything inside the size preset's safe margin |
| LR-G004 | no overlapping boxes |
| LR-B001–B004 | node, edge, accent and callout budgets for the diagram type |
| LR-C001 | right-angle connectors only |
| LR-C002 | edge labels masked and 6–10px off their own line |
| LR-C003 | no two connectors run on top of (or within 12px of) each other |
| LR-C004 | attach points on one box side ≥ 12px apart (8px on small boxes), ≥ 8px from corners |
| LR-C005 | no connector passes behind a box that is not its endpoint |
| LR-C006 | edge labels don't cover boxes |
| LR-C007 | edge labels ≤ 14 chars, uppercase (warn) |
| LR-T001 | colours come from the theme palette |
| LR-T002 | fonts come from the theme |
| LR-T005 | no shadows, glass or gradients |
| LR-L001 | the legend covers exactly the treatments and edge kinds used |
| LR-X001 | links are `https:`, `mailto:` or internal page links only |
| LR-X002 | images are embedded data URIs or draw.io built-in library paths |
| LR-I001 | every AWS / GCP / Azure / Kubernetes shape is in the verified catalog (otherwise draw.io may draw an empty box; `warn` on other files) |
| LR-I002 | one icon family per platform (e.g. not `gcp` with `gcp3`) |
| LR-I007 | info: vendor icons keep official colours, so they are exempt from LR-T001 |

Exit codes: 0 clean, 1 errors (or warnings with `--strict`), 2 unreadable input.
