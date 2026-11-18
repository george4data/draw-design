# Flowchart

**Use when** you show decision logic: a process with branches, where questions decide the path.
**Don't use** for handoffs between teams (swimlane, planned), message timing (sequence, planned), or a straight list of steps (write a numbered list).

## Layout grammar

- Shapes carry the type: `start` / `end` are pills, `decision` is a diamond (phrase it as a short question ending in `?`), `step` (default) is a box.
- Flow runs top → down (`TB` default). The compiler falls back to `LR` when TB does not fit the preset.
- **Every exit of a decision is labelled** (`YES` / `NO`, or the short answer). A decision has at most 3 exits.
- Convention: **YES exits right, NO exits below.** The compiler places YES targets beside the decision and NO targets under it automatically when the labels are YES/NO.
- Accent: the happy path (`kind: accent` on its key edge) **or** the single most important decision/outcome (`focal`), not both.

## Spec example

```json
{
  "ddVersion": 1, "type": "flowchart", "title": "Refund approval",
  "description": "A refund request is checked against the order age and amount; small recent refunds are approved automatically, others go to a reviewer.",
  "nodes": [
    { "id": "start", "label": "Refund requested", "role": "start" },
    { "id": "age", "label": "Within 30 days?", "role": "decision" },
    { "id": "amount", "label": "Under $100?", "role": "decision" },
    { "id": "auto", "label": "Auto-approve", "sublabel": "refund-svc", "focal": true },
    { "id": "review", "label": "Manual review", "sublabel": "support queue" },
    { "id": "deny", "label": "Deny with reason", "role": "end" }
  ],
  "edges": [
    { "from": "start", "to": "age" },
    { "from": "age", "to": "amount", "label": "YES" },
    { "from": "age", "to": "deny", "label": "NO" },
    { "from": "amount", "to": "auto", "label": "YES", "kind": "accent" },
    { "from": "amount", "to": "review", "label": "NO" }
  ]
}
```

## Budget

≤ 9 nodes, ≤ 12 edges, ≤ 3 exits per decision, ≤ 2 accents. Long processes: split into phases, one flowchart each.

## Anti-patterns

- Colour as type (shape already says it).
- Unlabelled decision exits.
- Diamonds that ask "which service?": that is an architecture diagram drawn with the wrong shapes.
- Loops drawn back to the top for retries: prefer an annotation callout ("retries up to 3×") unless the loop is the point.
