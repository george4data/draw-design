# Layer stack

**Use when** you show stacked abstraction levels where each layer builds on the one below: a tech stack, protocol layers, a platform architecture seen as tiers.
**Don't use** when components talk to each other across tiers in specific ways (architecture).

## Layout grammar

- Nodes are layers, listed **top to bottom** in reading order (the user-facing layer first). Each renders as a full-width band.
- `tag` holds the index (`L5` … `L1`), `label` the layer name, `sublabel` its contents in a few words.
- Use roles for meaning: `store` for data layers, `external` for layers you buy rather than build.
- Accent the one layer the story is about (where the change happens, or the bottleneck).
- Edges are usually unnecessary: adjacency already says "builds on".

## Spec example

```json
{
  "ddVersion": 1, "type": "layers", "title": "Agent platform stack",
  "description": "An agent platform stacks the user interface on orchestration, tools, models and the data layer.",
  "nodes": [
    { "id": "ui", "label": "Chat and IDE surfaces", "sublabel": "web · vscode · slack", "tag": "L4" },
    { "id": "orch", "label": "Orchestration", "sublabel": "planner · memory · policies", "tag": "L3", "focal": true },
    { "id": "models", "label": "Models", "sublabel": "hosted LLM APIs", "tag": "L2", "role": "external" },
    { "id": "data", "label": "Data", "sublabel": "vector store · warehouse", "tag": "L1", "role": "store" }
  ]
}
```

## Budget

4–6 layers, ≤ 2 accents. More than 6: merge adjacent layers or split.
