# Vendor icons (AWS, Google Cloud, Azure, Kubernetes)

Nodes in `architecture` and `sequence` diagrams can show the official service icon at their left. draw.io ships every icon library, so nothing is downloaded and the user enables nothing. The file references draw.io's own shapes, and the person editing it can swap them in draw.io.

## When to use icons

- **Use them** when the system runs on a cloud platform and the reader knows that platform's services. Typical cases: infrastructure, deployment and service architecture, and request flows through managed services.
- **Skip them** for logical or conceptual diagrams, audiences who don't know the platform, and every type other than `architecture` and `sequence`.
- **All or none.** Every service node gets an icon, or none does. Externals (`external`), clients (`input`) and actors (`actor`) are exempt and may go without.
- **One family per platform.** Never mix `gcp` with `gcp3` (or `aws4` with anything else for AWS). Different cloud platforms in one diagram are fine (multi-cloud).

## Workflow

1. **Find the platform** from the request and the repo:
   - Terraform providers (`aws`, `google`, `azurerm`) and resource prefixes (`aws_`, `google_`, `azurerm_`);
   - CloudFormation or CDK, `serverless.yml`, Kubernetes manifests;
   - how the user names their services.
2. **Look up every id. Never guess.** draw.io draws an empty box for an unknown name, so the build rejects ids that are not in the catalog.

   ```bash
   <skill-dir>/bin/ddraw icons search "sqs queue" --platform aws
   <skill-dir>/bin/ddraw icons search postgres --platform gcp --json
   <skill-dir>/bin/ddraw icons families          # what exists, and which family can be monochrome
   ```

   Search knows everyday words: `postgres` finds RDS, Aurora and Cloud SQL, `redis` finds ElastiCache and Memorystore, and `bucket` finds S3 and Cloud Storage.
3. **Put the ids in the spec:** `"icon": "aws4:lambda"` on a node, or on a sequence participant.
   - The icon replaces the node's `tag`, so drop the tag.
   - Keep the human name in `label` and the technical detail in `sublabel` (e.g. `"label": "Payments", "sublabel": "Lambda"`).
4. **Build.** `LR-I001` means an unknown id; its fix suggests the nearest real ids.

## Families

| Family | Platform | Use |
|---|---|---|
| `aws4` | AWS | the current AWS architecture icons (resource tiles and glyphs) |
| `gcp` | Google Cloud | the Google Cloud product icons (multicolour); **default for GCP** |
| `gcp3` | Google Cloud | Google's 2026 icon set: only 45 icons, mostly categories and a few core products. Use it only if every node is covered |
| `gcp2` | Google Cloud | legacy generic stencils; avoid |
| `azure2` | Azure | Azure service icons |
| `kubernetes` | Kubernetes | resource icons: `pod`, `deploy`, `svc`, `ing`, `sts`, `cm`, `secret`, `pv`, `ns`, … |

## Colour

- `"iconStyle": "vendor"` (the default) keeps official colours. Lint reports this as `LR-I007` (info); it is not an error.
- `"iconStyle": "mono"` tints the icon to the theme's muted ink for a quieter, on-brand page.
  - Only `aws4` and `kubernetes` can be recoloured. Other families keep vendor colours, with warning `LR-I004`.
  - Vendor guidelines generally discourage altering icons, so keep `vendor` for anything published alongside the vendor's brand.

## Example

```json
{ "id": "pay", "label": "Payments", "sublabel": "Lambda", "zone": "core", "icon": "aws4:lambda" }
```

`examples/architecture-aws.dd.json` is a complete AWS architecture.

## Not built yet

Say so in one line if asked:

- **Zone icons:** vendor group containers such as an AWS VPC or region, or a GCP project.
- **Standalone icons:** the icon as the node, with the label below.
- **Generic icons:** user, database and queue for diagrams not tied to a cloud.
- **Importing extra icon packs.**
