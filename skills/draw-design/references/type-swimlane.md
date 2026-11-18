# Swimlane

**Use when** a process crosses teams, systems or people and the **handoffs between them** are the story (waiting, rework, approvals).
**Don't use** for decision-heavy logic inside one team (flowchart), or for message timing between services (sequence).

## Layout grammar

- **Lanes are `zones`**, one per actor, listed top to bottom. Every node sets `zone` to the lane that performs the step. A step never spans two lanes.
- Columns are steps in time. Work that stays inside a lane moves one column right; **a handoff to another lane drops straight down or up in the same column**, so every handoff is a short vertical arrow. Override a column with `place.step` (0-based) when you need to align things.
- Accent the costliest or slowest handoff (`kind: accent` on that edge) or the step where work waits (`focal`).
- Label handoffs only when the channel matters (`EMAIL`, `TICKET`, `HANDOFF`).
- `role: input` marks the customer's own actions; `role: external` marks steps done by an outside party.

## Spec example

```json
{
  "ddVersion": 1, "type": "swimlane", "title": "Refund handling",
  "description": "A customer refund request moves from support triage to finance approval and back to the customer.",
  "zones": [ { "id": "customer", "label": "Customer" }, { "id": "support", "label": "Support" }, { "id": "finance", "label": "Finance" } ],
  "nodes": [
    { "id": "request", "label": "Request refund", "role": "input", "zone": "customer" },
    { "id": "triage", "label": "Triage ticket", "zone": "support" },
    { "id": "approve", "label": "Approve payout", "sublabel": "≤ 2 days", "zone": "finance", "focal": true },
    { "id": "notify", "label": "Notify customer", "zone": "support" }
  ],
  "edges": [
    { "from": "request", "to": "triage" },
    { "from": "triage", "to": "approve", "label": "HANDOFF", "kind": "accent" },
    { "from": "approve", "to": "notify" }
  ]
}
```

## Budget

≤ 5 lanes, ≤ 9 steps, ≤ 12 edges, ≤ 2 accents. Long processes: split by phase.

## Anti-patterns

- Snaking flows that go back and forth across many columns: reorder steps or split the process.
- A lane for a system nobody owns: lanes are owners.
