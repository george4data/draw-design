# Architecture

**Use when** you show components and their connections in one snapshot: services, stores, clients and external systems, grouped into tiers or trust boundaries.
**Don't use** for message order over time (sequence, planned), a single process with decisions (flowchart), or before/after topology changes (architecture delta, planned).

## Layout grammar

- One flow direction for the whole diagram. `LR` (default) reads clients → edge → services → data. `TB` suits tall stacks.
- **Zones** group nodes by tier or trust boundary (≤ 3 flat zones). Members of a zone occupy adjacent ranks. Nodes outside every zone (third parties) sit after the last zone.
- **Focal**: the one component the story is about (the new service, the bottleneck, the entry point). Optionally make the headline request path an `accent` edge, but stay within 2 accents total.
- Treatments: clients/users `input`, databases/queues/caches `store`, third-party services `external`, everything you run `backend`, firewalls/IdP boundaries `security`.
- Label only edges whose meaning is not obvious: protocols (`HTTPS`, `GRPC`, `SQL`) or verbs (`PUBLISHES`, `CHARGE`).

## Spec example

```json
{
  "ddVersion": 1, "type": "architecture", "title": "Checkout platform",
  "description": "Requests from web and mobile clients pass through an API gateway to the order and payment services, which persist to Postgres.",
  "zones": [{ "id": "clients", "label": "Clients" }, { "id": "core", "label": "Core services" }, { "id": "data", "label": "Data" }],
  "nodes": [
    { "id": "web", "label": "Web App", "sublabel": "next.js", "role": "input", "zone": "clients" },
    { "id": "gw", "label": "API Gateway", "sublabel": "nginx · :443", "tag": "EDGE", "zone": "core", "focal": true },
    { "id": "orders", "label": "Orders", "sublabel": "grpc :9001", "tag": "API", "zone": "core" },
    { "id": "pg", "label": "Postgres", "role": "store", "tag": "DB", "zone": "data" },
    { "id": "stripe", "label": "Stripe", "role": "external", "tag": "EXT" }
  ],
  "edges": [
    { "from": "web", "to": "gw", "label": "HTTPS", "kind": "link" },
    { "from": "gw", "to": "orders", "kind": "accent" },
    { "from": "orders", "to": "pg", "label": "SQL" },
    { "from": "orders", "to": "stripe", "label": "CHARGE", "kind": "link" }
  ]
}
```

## Budget

≤ 9 nodes, ≤ 12 edges, ≤ 3 zones, ≤ 2 accents. Over budget: split into an overview (zones as nodes) and one detail diagram per zone.

## Anti-patterns

- Every service in its own zone: zones are tiers or trust boundaries, not decoration.
- Accent on every "important" node: pick the one the story is about.
- Edges for relationships the layout already shows (A above B in a stack where everything flows down).
- Vendor product names at `audience: executive`: name capabilities instead.

## draw.io notes

Zones are draw.io containers, so moving a zone moves its members. Edges carry explicit waypoints with `orthogonalEdgeStyle`; dragging a node in draw.io re-routes the edge orthogonally. Node metadata (`dd-*`) appears under *Edit Data*.
