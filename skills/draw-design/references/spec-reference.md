# Diagram Spec reference (`*.dd.json`)

The spec is the only thing you write. `ddraw build` validates it strictly: **unknown keys are errors**, and every error carries a JSON pointer and a fix. Print the full schema with `ddraw schema`.

## Top level

| Key | Required | Default | Notes |
|---|---|---|---|
| `ddVersion` | yes | — | always `1` |
| `type` | yes | — | a shipped type (`ddraw types`) |
| `title` | yes | — | 1–60 chars; the diagram's headline and page name |
| `description` | yes | — | one sentence about the **content** (10–200 chars), not the geometry. Used as the accessible description in exports |
| `eyebrow` | no | type name | small uppercase label above the title |
| `subtitle` | no | — | ≤ 120 chars |
| `size` | no | `doc-inline` | `doc-inline` 960×600 · `doc-wide` 1280×720 · `slide-16x9` 1280×720 (bigger type) · `slide-4x3` · `social-og` · `social-square` · `print-a4-landscape` · `print-a3-landscape` · `print-letter-landscape` · `fit` (frame grows to the content) |
| `direction` | no | type default | `LR` or `TB` (also `RL`, `BT`). Leave it out to let the compiler try the type default, then the alternative |
| `detail` | no | `balanced` | `simplified` (≤ 7 nodes) · `balanced` (≤ 12) · `faithful` (≤ 24, zones required above 9) |
| `audience` | no | `mixed` | `engineer` · `mixed` · `executive`: governs wording, which is your job |
| `nodes`, `edges`, `zones`, `callouts` | — | `[]` | below |
| `legend` | no | `"auto"` | `false` to suppress |
| `iconStyle` | no | `vendor` | `vendor` (official colours) or `mono` (theme ink; `aws4` and `kubernetes` only). Only with node icons |

## Nodes

```json
{ "id": "gw", "label": "API Gateway", "sublabel": "nginx · :443", "role": "backend", "tag": "EDGE", "zone": "core", "focal": true }
```

- `id`: lowercase `a-z0-9-`, starts with a letter, unique across nodes, zones and edges.
- `label` ≤ 32 chars (the name a human uses). `sublabel` ≤ 40 chars (the technical detail, monospace).
- `role`: `backend` (default), `store`, `external`, `input`, `optional`, `security`, plus type-specific roles.
- `tag` ≤ 6 alphanumerics (`API`, `DB`, `EXT`, `EDGE`), shown as a small rectangular tag.
- `focal`: accent treatment. Combined with accent edges, at most 2.
- `icon` (`architecture`, `sequence`): a vendor icon id such as `aws4:lambda` or `gcp:cloud_run`, drawn at the node's left. It replaces `tag`. Get ids from `ddraw icons search`; never guess. See [icons.md](icons.md).
- `place`: layout hints. `{"rank": n}` puts the node in column/row *n* along the flow; `{"order": n}` orders nodes inside a rank. Use them only to fix a layout you don't like.
- `meta`: up to 12 string key/values stored on the shape (draw.io *Edit Data*). `"url": "https://…"` becomes a clickable link.

## Edges

```json
{ "from": "orders", "to": "pg", "label": "SQL", "kind": "default" }
```

- `label` ≤ 14 chars, rendered uppercase. Only label edges where the label adds information.
- `kind`: `default` · `accent` (headline path; counts toward the accent limit) · `link` (HTTP/API/external) · `async` (dashed, open arrow) · `return` (dashed).
- `bidirectional: true` draws arrowheads on both ends. Prefer one direction.
- `fromSide` / `toSide` (`top|right|bottom|left`): routing hints when the automatic side is wrong.

## Zones

```json
{ "id": "core", "label": "Core services", "role": "zone" }
```

Containers drawn behind their members (`node.zone`). `role: security` draws a dashed accent boundary. Zones nest with `parent`. Keep zones to ≤ 3. Members of one zone should sit in adjacent ranks. If zones overlap, the build fails with `LAYOUT-002`: give the members distinct `place.rank` values or merge the zones.

## Callouts

`{"text": "single point of failure", "target": "gw", "corner": "tr"}`: an italic editorial aside placed in a margin corner. At most 2. Use them for the one thing the diagram cannot say with structure.

## Reading build errors

| Code | Meaning | Usual fix |
|---|---|---|
| `SPEC-0xx` | schema or reference error at the pointer | fix the key/value named in the message |
| `LR-B001/2/3` | over the node / edge / accent budget | merge, cut, or split into overview + detail |
| `TEXT-001` | a label cannot fit the widest box | shorten it |
| `LAYOUT-001` | does not fit the size preset | larger preset, other direction, lower detail, or split |
| `LAYOUT-002/3` | zones overlap / a non-member sits inside a zone | adjust `place.rank`, membership, or merge zones |
| `ROUTE-001/2` | no clean route / no room for a label | `fromSide`/`toSide` hints, drop or shorten the label, larger preset |
| `LR-*` | lint rule on the emitted file (see `references/lint.md`) | follow the fix text |
