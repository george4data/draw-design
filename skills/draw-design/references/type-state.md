# State machine

**Use when** one subject moves between states as events happen (an order, a ticket, a job, a session), and guards or actions matter.
**Don't use** for decision logic without persistent states (flowchart), or for message order between actors (sequence, planned).

## Layout grammar

- Roles: `initial` (filled dot, exactly one), `state` (default, rounded box), `final` (ringed dot, at most one; route every terminal state into it), plus `optional` for exceptional states such as `Cancelled`, and `external` for states owned by another system.
- Flow runs left → right (`LR`) by default; `TB` for long lifecycles.
- Transition labels use the UML form **`event [guard] / action`**, up to 28 characters, lowercase allowed (`pay / capture`, `timeout [24h]`, `retry [attempts < 3]`).
- **Self-transitions** are allowed (`from` = `to`) and draw as a small loop above the state.
- Accent: the state the story is about (the happy completion, or the error state), not both.
- Put the state's machine name in `sublabel` when engineers will read it (`awaiting_payment`).

## Spec example

```json
{
  "ddVersion": 1, "type": "state", "title": "Order lifecycle", "size": "doc-wide",
  "description": "An order waits for payment, is paid, shipped and delivered; unpaid orders time out and are cancelled.",
  "nodes": [
    { "id": "start", "label": "Created", "role": "initial" },
    { "id": "pending", "label": "Pending payment", "sublabel": "awaiting_payment" },
    { "id": "paid", "label": "Paid" },
    { "id": "delivered", "label": "Delivered", "focal": true },
    { "id": "cancelled", "label": "Cancelled", "role": "optional" },
    { "id": "done", "label": "Closed", "role": "final" }
  ],
  "edges": [
    { "from": "start", "to": "pending" },
    { "from": "pending", "to": "pending", "label": "retry [attempts < 3]" },
    { "from": "pending", "to": "paid", "label": "pay / capture" },
    { "from": "pending", "to": "cancelled", "label": "timeout [24h]" },
    { "from": "paid", "to": "delivered", "label": "deliver" },
    { "from": "delivered", "to": "done" },
    { "from": "cancelled", "to": "done" }
  ]
}
```

## Budget

≤ 9 states (incl. initial/final), ≤ 12 transitions, ≤ 2 accents. Long lifecycles with many states fit better at `doc-wide`. Keep transitions ≤ 2× states; "from any state" transitions become one callout (`* → Error on failure`), not a fan of edges.

## Anti-patterns

- A state per screen or per function call: states are stable conditions, not steps.
- Transitions without events.
- Several final markers: route terminal states into one.
