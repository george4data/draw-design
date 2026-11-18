# Tree

**Use when** you show a strict parent → children hierarchy: a taxonomy, a work breakdown, a package or file tree.
**Don't use** when a node has several parents or there are cycles (architecture or dependency graph), or for people and ownership (org chart).

## Layout grammar

- Edges go **from parent to child**. Each node has at most one parent; the root has none.
- Tidy layout: leaves keep their declaration order and each parent is centred over its children. Declare children in the order you want them read.
- Connectors are **bus connectors**: parent drop → shared horizontal bus → child drops. They carry no labels; the hierarchy is the message.
- `TB` by default; `LR` for deep, narrow trees (the compiler falls back to LR when TB does not fit).
- Accent on one node: the root, or the one leaf the story is about.

## Spec example

```json
{
  "ddVersion": 1, "type": "tree", "title": "Platform monorepo",
  "description": "The platform monorepo splits into apps, shared packages and infrastructure, each with its own modules.",
  "nodes": [
    { "id": "root", "label": "platform", "sublabel": "pnpm workspace", "focal": true },
    { "id": "apps", "label": "apps" }, { "id": "packages", "label": "packages" },
    { "id": "web", "label": "web", "sublabel": "next.js" }, { "id": "ui", "label": "ui", "sublabel": "design system" }
  ],
  "edges": [
    { "from": "root", "to": "apps" }, { "from": "root", "to": "packages" },
    { "from": "apps", "to": "web" }, { "from": "packages", "to": "ui" }
  ]
}
```

## Budget

≤ 9 nodes, depth ≤ 4, ≤ 5 children per node, ≤ 2 accents. Wider or deeper: show the top levels and split subtrees into their own diagrams.

## Anti-patterns

- More than two node widths: the compiler uses one width; keep labels similar in length.
- Diagonal "mind map" spokes: trees use orthogonal bus connectors.
