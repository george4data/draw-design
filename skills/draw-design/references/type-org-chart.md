# Org chart

**Use when** you show who owns, routes or escalates what: teams, people or agents, reporting lines and escalation paths.
**Don't use** for software component hierarchies (tree) or for process handoffs (flowchart, swimlane planned).

## Layout grammar

- The front door (where work enters) is the root at the top centre and is usually the focal node.
- Each node: `label` = owner (team, person or agent), `sublabel` = how to reach it or its scope in 2–4 words (`#help · triage`, `refunds, invoices`).
- Not-yet-live owners use `role: optional` (dashed). Third parties use `role: external`.
- Bus connectors with no labels; escalation rules that don't fit the hierarchy go in a callout (`callouts`), not in extra nodes.

## Spec example

```json
{
  "ddVersion": 1, "type": "org-chart", "title": "Support escalation",
  "description": "Customer requests enter through the support desk, which routes them to billing or technical support, with engineering on call behind technical support.",
  "nodes": [
    { "id": "desk", "label": "Support desk", "sublabel": "#help · triage", "focal": true },
    { "id": "billing", "label": "Billing team", "sublabel": "refunds, invoices" },
    { "id": "tech", "label": "Technical support", "sublabel": "bugs, outages" },
    { "id": "oncall", "label": "Engineering on-call", "sublabel": "pager" }
  ],
  "edges": [
    { "from": "desk", "to": "billing" }, { "from": "desk", "to": "tech" }, { "from": "tech", "to": "oncall" }
  ]
}
```

## Budget

≤ 12 nodes, depth ≤ 4, ≤ 5 direct reports per node (more: group them into pods), ≤ 2 callouts.
