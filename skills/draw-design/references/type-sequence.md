# Sequence

**Use when** you show time-ordered messages between a few actors and services: a login flow, an API call chain, a webhook handshake.
**Don't use** for decisions without actors (flowchart), states of one object (state), or static structure (architecture).

## Spec block

Sequence diagrams use a `sequence` block **instead of** `nodes`/`edges`:

```json
{
  "ddVersion": 1, "type": "sequence", "title": "OAuth authorization code flow", "size": "doc-wide",
  "description": "A browser signs in through the web app, which exchanges an authorization code for a token and then calls the API with it.",
  "sequence": {
    "participants": [
      { "id": "user", "label": "Browser", "role": "actor" },
      { "id": "app", "label": "Web App", "sublabel": "next.js" },
      { "id": "auth", "label": "Auth Server", "sublabel": "OIDC", "role": "external" }
    ],
    "messages": [
      { "from": "user", "to": "app", "label": "GET /login" },
      { "from": "app", "to": "auth", "label": "POST /token", "focal": true },
      { "from": "auth", "to": "app", "label": "access token", "kind": "return" },
      { "from": "app", "to": "app", "label": "check state" },
      { "from": "app", "to": "user", "label": "session cookie", "kind": "return" }
    ],
    "fragments": [
      { "kind": "opt", "label": "no cached token", "from": 2, "to": 3 }
    ]
  }
}
```

- `participants`, left to right in reading order. `role`: `actor` (people, browsers), `service` (default), `store`, `external`. `focal: true` accents a participant.
- `messages`, in time order. `kind`: `sync` (default: solid line, filled arrow; starts an activation bar on the receiver), `return` (dashed, filled arrow; ends the receiver's activation), `async` (dashed, open arrow). `from` = `to` draws a self-message loop. `focal: true` draws the headline message in the accent colour. Labels ≤ 24 chars and keep their case (`POST /token`, `200 profile`).
- `fragments` wrap a range of messages, **numbered from 1**: `opt` (optional), `loop`, `alt` (with `elseAt` = the first message of the else region and `elseLabel`). `label` is the guard, shown as `[guard]`. Fragments nest or are disjoint; at most 1 nesting level.

## Layout grammar

- Participants are native draw.io lifelines (header plus dashed line). Messages are attached to them, so moving a lifeline in draw.io keeps the messages connected.
- Activation bars are computed from sync calls and their matching returns. Pair every sync call that needs a reply with a `return` message.
- No upward messages: order is time.
- One accent: the headline message (often the token exchange or the failing call), or a focal participant.

## Budget

≤ 5 participants, ≤ 12 messages, ≤ 2 fragments, `alt` ≤ 2 regions, nesting ≤ 1, ≤ 2 accents. A typical 4-participant, 9-message flow needs `doc-wide`. Longer flows: split into phases, one diagram each.

## Anti-patterns

- A message for every function call: show the conversation between components, not the call stack.
- Returns drawn as solid lines.
- `par`, `break` and other fragments: not supported. Split the diagram or use a callout.
