#!/usr/bin/env python3
"""Build the vendor shape catalog in skills/draw-design/data/shapes/ (PRD §10.8.3, FR-132).

Maintenance script, not run by end users. Input is jgraph/drawio-mcp's shape-search index
(Apache-2.0; generated from draw.io's own sidebar definitions), pinned to a commit. With
--verify, every entry is rendered by the installed draw.io Desktop and dropped if it does not
draw; the catalog then records the draw.io version it was verified with.

    python3 scripts/build-shape-catalog.py --fetch --verify
    python3 scripts/build-shape-catalog.py --index search-index.json --verify
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "draw-design"
sys.path.insert(0, str(SKILL / "scripts"))

from ddraw.export import drawio_cli  # noqa: E402

PINNED_SHA = "cfc1b916b9deaa7c78d23d719d4124bd76d2d0bf"
INDEX_URL = "https://raw.githubusercontent.com/jgraph/drawio-mcp/{sha}/shape-search/search-index.json"

# family → (title, platform, current, recolor, note)
FAMILIES: dict[str, tuple[str, str, bool, str, str]] = {
    "aws4": ("AWS architecture icons", "aws", True, "fill", "Amazon Web Services architecture icons"),
    "gcp": ("Google Cloud product icons", "gcp", True, "none", "Google Cloud product icons (multicolour)"),
    "gcp3": ("Google Cloud 2026 icons", "gcp", True, "none", "Google Cloud 2026 category and core icons"),
    "gcp2": ("Google Cloud (legacy stencils)", "gcp", False, "none", "older GCP stencils, mostly generic"),
    "azure2": ("Microsoft Azure", "azure", True, "none", "Azure icons (draw.io built-in images)"),
    "kubernetes": ("Kubernetes", "kubernetes", True, "fill", "Kubernetes resource icons"),
}
# Preferred family per platform when several match (search ranking).
PREFERRED = {
    "aws": ["aws4"],
    "gcp": ["gcp", "gcp3", "gcp2"],
    "azure": ["azure2"],
    "kubernetes": ["kubernetes"],
}

GCP_CATEGORIES = [
    "Ai Machine Learning",
    "Api Management",
    "Data Analytics",
    "Developer Tools",
    "Hybrid And Multi Cloud",
    "Integration Services",
    "Management Tools",
    "Compute",
    "Databases",
    "Iot",
    "Migration",
    "Networking",
    "Operations",
    "Security",
    "Serverless",
    "Storage",
]
BOILERPLATE = {
    "aws",
    "aws4",
    "amazon",
    "web",
    "service",
    "services",
    "gcp",
    "gcp2",
    "gcp3",
    "gcpicons",
    "google",
    "platform",
    "icons",
    "icon",
    "azure",
    "azure2",
    "microsoft",
    "kubernetes",
    "k8s",
}
# draw.io's GCP titles spell out acronyms ("Api Gateway Application Programming Interface").
EXPANSIONS = {
    "api": "application programming interface",
    "apis": "application programming interfaces",
    "ai": "artificial intelligence",
    "cdn": "content domain network",
    "dns": "domain name server",
    "ip": "internet protocol",
    "vpn": "virtual private network",
    "ide": "integrated development environment",
    "iot": "internet of things",
    "alloydb": "alloy database",
    "nat": "network address translation",
    "gpu": "graphics processing unit",
    "tpu": "tensor processing unit",
    "vm": "virtual machine",
    "iam": "identity and access management",
    "kms": "key management service",
    "os": "operating system",
    "ad": "advertisement",  # draw.io's expansion of "Managed MS AD" (Active Directory) is wrong
}


def clean_title(title: str) -> str:
    words = title.lower().split()
    text = " ".join(words)
    for acro, phrase in EXPANSIONS.items():
        if phrase in text and (acro in words or acro in text.replace(" ", "")):
            text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("api "):
        text = "api " + text[4:]
    return text or title.lower()


# Everyday words agents use for common services (search weights them like title words).
ALIASES: dict[str, list[str]] = {
    "aws4:s3": ["bucket", "object", "storage", "blob"],
    "aws4:rds": ["postgres", "postgresql", "mysql", "sql", "relational", "database"],
    "aws4:aurora": ["postgres", "postgresql", "mysql", "sql", "relational", "database"],
    "aws4:dynamodb": ["nosql", "key", "value", "database"],
    "aws4:elasticache": ["redis", "memcached", "cache"],
    "aws4:sqs": ["queue"],
    "aws4:sns": ["pubsub", "notification", "topic", "fanout"],
    "aws4:eventbridge": ["event", "bus", "events"],
    "aws4:cloudfront": ["cdn"],
    "aws4:api_gateway": ["api", "rest", "http"],
    "aws4:cognito": ["auth", "login", "identity", "users"],
    "aws4:fargate": ["container", "containers", "docker", "serverless"],
    "aws4:ecs": ["container", "containers", "docker"],
    "aws4:eks": ["kubernetes", "k8s", "cluster"],
    "aws4:route_53": ["dns", "domain"],
    "aws4:application_load_balancer": ["load", "balancer", "alb", "lb"],
    "aws4:kinesis": ["stream", "streaming"],
    "aws4:managed_streaming_for_kafka": ["kafka", "msk", "stream"],
    "aws4:elasticsearch_service": ["opensearch", "elasticsearch", "search"],
    "aws4:secrets_manager": ["secret", "secrets", "vault"],
    "aws4:cloudwatch_2": ["cloudwatch", "monitoring", "metrics", "logs"],
    "aws4:step_functions": ["workflow", "orchestration"],
    "aws4:users": ["user", "people", "customer"],
    "aws4:client": ["browser", "web", "desktop"],
    "aws4:mobile_client": ["mobile", "phone", "app"],
    "gcp:cloud_sql": ["postgres", "postgresql", "mysql", "relational", "database"],
    "gcp:memorystore": ["redis", "cache"],
    "gcp:pub_sub": ["queue", "topic", "pubsub", "events"],
    "gcp:cloud_storage": ["bucket", "object", "storage", "blob", "gcs"],
    "gcp:google_kubernetes_engine": ["gke", "kubernetes", "k8s", "cluster"],
    "gcp:cloud_load_balancing": ["load", "balancer", "lb"],
    "gcp:cloud_cdn": ["cdn"],
    "gcp:cloud_run": ["container", "containers", "serverless", "service"],
    "gcp:cloud_functions": ["function", "serverless", "lambda"],
    "gcp:firestore": ["nosql", "document", "database"],
    "gcp:bigquery": ["warehouse", "analytics", "sql"],
    "azure2:azure_cosmos_db": ["nosql", "document", "database"],
    "azure2:azure_database_postgresql_server": ["postgres", "postgresql", "database"],
    "azure2:cache_redis": ["redis", "cache"],
    "azure2:storage_accounts": ["bucket", "blob", "storage"],
    "azure2:function_apps": ["function", "serverless", "lambda"],
    "azure2:kubernetes_services": ["aks", "kubernetes", "k8s", "cluster"],
    "azure2:app_services": ["web", "app", "service"],
}

SKIP_AWS_SHAPES = {"resourceIcon", "productIcon", "group", "groupCenter", "illustration"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def style_value(style: str, key: str) -> str:
    m = re.search(rf"(?:^|;){re.escape(key)}=([^;]*)", style)
    return m.group(1) if m else ""


def classify(e: dict[str, Any]) -> tuple[str, str, str] | None:
    """(family, name, kind) for an index entry, or None to skip it."""
    st, tags = e["style"], e.get("tags", "")
    if e.get("type") == "edge":
        return None
    shape = style_value(st, "shape")
    if shape.startswith("mxgraph.aws4."):
        sub = shape[len("mxgraph.aws4.") :]
        if sub == "resourceIcon":
            return "aws4", style_value(st, "resIcon").rsplit(".", 1)[-1], "icon"
        if sub == "group":
            return "aws4", style_value(st, "grIcon").rsplit(".", 1)[-1], "group"
        if sub in SKIP_AWS_SHAPES or sub.startswith("illustration"):
            return None
        return "aws4", sub, "icon"
    for fam in ("gcp3", "gcp2", "kubernetes"):
        if shape.startswith(f"mxgraph.{fam}."):
            name = style_value(st, "prIcon") or shape.split(".", 2)[2]
            return fam, name, "icon"
    image = style_value(st, "image")
    if image.startswith("img/lib/azure2/"):
        return "azure2", slug(Path(image).stem), "icon"
    if "shape=image" in st and image.startswith("data:image/") and tags.startswith("gcp2 "):
        title = e["title"].strip()
        for cat in GCP_CATEGORIES:
            if title.lower().startswith(cat.lower() + " ") and len(title) > len(cat) + 1:
                title = title[len(cat) + 1 :]
                break
        return "gcp", slug(clean_title(title)), "icon"
    return None


def display_title(fam: str, name: str, raw: str) -> str:
    if fam == "gcp":
        words = name.split("_")
        upper = {
            "api",
            "apis",
            "ai",
            "cdn",
            "dns",
            "ip",
            "vpn",
            "ide",
            "iot",
            "nat",
            "gpu",
            "tpu",
            "iam",
            "dr",
            "sql",
            "os",
            "ms",
            "ad",
        }
        return " ".join(w.upper() if w in upper else w.capitalize() for w in words)
    return re.sub(r"\s+", " ", raw).strip() or name.replace("_", " ").title()


def preference(e: dict[str, Any], kind: str) -> tuple[int, int]:
    """Lower sorts first: coloured icon tiles over white ones; light group variants over dark."""
    st, tags = e["style"], e.get("tags", "")
    white = style_value(st, "fillColor").lower() in ("#ffffff", "#fff")
    dark = " dark " in f" {tags} "
    return (int(dark) if kind == "group" else int(white), 0)


def collect(index: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {f: {} for f in FAMILIES}
    ranked: dict[tuple[str, str], tuple[tuple[int, int], int]] = {}
    for order, e in enumerate(index):
        c = classify(e)
        if c is None:
            continue
        fam, name, kind = c
        name = slug(name)
        if not name:
            continue
        key = (fam, name)
        rank = (preference(e, kind), order)
        if key in ranked and ranked[key] <= rank:
            continue
        ranked[key] = rank
        words = [w for w in re.split(r"[^a-z0-9]+", e.get("tags", "").lower()) if w and w not in BOILERPLATE]
        tags = list(dict.fromkeys(words))[:16]
        out[fam][name] = {
            "id": f"{fam}:{name}",
            "title": display_title(fam, name, e["title"]),
            "tags": tags,
            "kind": kind,
            "w": round(float(e["w"]), 1),
            "h": round(float(e["h"]), 1),
            "style": e["style"],
        }
    return out


def verify(entries: list[dict[str, Any]], cli: drawio_cli.Cli) -> set[str]:
    """Render every entry once; return the ids that drew something."""
    cells = []
    for i, e in enumerate(entries):
        x, y = (i % 40) * 90, (i // 40) * 90
        st = html.escape(e["style"], quote=True)
        cells.append(
            f'<mxCell id="c{i}" value="" style="{st}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="60" height="60" as="geometry"/></mxCell>'
        )
    xml = (
        '<mxfile><diagram id="v" name="V"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "verify.drawio", Path(tmp) / "verify.svg"
        src.write_text(xml, encoding="utf-8")
        args = [*cli.wrapper, str(cli.path), "-x", "-f", "svg", "--embed-svg-images", "-o", str(out)]
        subprocess.run([*args, "--disable-update", str(src)], capture_output=True, timeout=600, check=True)
        svg = out.read_text(encoding="utf-8")
    bodies = {p[: p.index('"')]: p for p in svg.split('<g data-cell-id="')[1:]}
    ok = set()
    for i, e in enumerate(entries):
        body = bodies.get(f"c{i}", "")
        tags = set(re.findall(r"<(path|rect|ellipse|image|use)\b", body))
        if ("image=" in e["style"] and "shape=image" in e["style"]) or e["id"].startswith("azure2:"):
            drew = bool({"image", "use"} & tags) and "file:///" not in body
        else:
            drew = len(body) > 400 and tags != {"rect"}
        if drew:
            ok.add(e["id"])
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, help="local search-index.json")
    ap.add_argument(
        "--fetch", action="store_true", help=f"download the index at the pinned commit {PINNED_SHA[:10]}"
    )
    ap.add_argument("--sha", default=PINNED_SHA)
    ap.add_argument("--verify", action="store_true", help="render every entry with draw.io Desktop")
    ap.add_argument("--out", type=Path, default=SKILL / "data" / "shapes")
    a = ap.parse_args()
    if a.fetch:
        url = INDEX_URL.format(sha=a.sha)
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.URLError:
            # Some Python builds lack a CA bundle (macOS python.org installs); curl uses the system store.
            cmd = ["curl", "-sfL", "--max-time", "120", url]
            raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        index = json.loads(raw.decode("utf-8"))
    elif a.index:
        index = json.loads(a.index.read_text(encoding="utf-8"))
    else:
        ap.error("pass --fetch or --index")
    families = collect(index)
    verified_with = ""
    if a.verify:
        cli = drawio_cli.find()
        if cli is None:
            print("draw.io Desktop not found; set DRAWIO_CLI", file=sys.stderr)
            return 3
        verified_with = cli.version or "unknown"
        for fam, entries in families.items():
            ok = verify(list(entries.values()), cli)
            dropped = sorted(set(entries) - {i.split(":", 1)[1] for i in ok})
            for name in dropped:
                del entries[name]
            print(f"{fam:11} {len(entries):5} kept, {len(dropped)} dropped {dropped[:6]}")
    for icon_id, words in ALIASES.items():
        fam, name = icon_id.split(":", 1)
        if name in families[fam]:
            families[fam][name]["aliases"] = words
        else:
            print(f"warning: alias target {icon_id} is not in the catalog", file=sys.stderr)
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fam, entries in families.items():
        title, platform, current, recolor, note = FAMILIES[fam]
        data = [entries[k] for k in sorted(entries)]
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        (a.out / f"{fam}.json.gz").write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
        rows.append(
            {
                "family": fam,
                "title": title,
                "platform": platform,
                "current": current,
                "recolor": recolor,
                "count": len(data),
                "groups": sum(1 for d in data if d["kind"] == "group"),
                "note": note,
            }
        )
    meta = {
        "catalogVersion": 1,
        "source": {
            "repo": "https://github.com/jgraph/drawio-mcp",
            "path": "shape-search/search-index.json",
            "commit": a.sha if (a.fetch or a.index) else "",
            "license": "Apache-2.0",
        },
        "verifiedWith": verified_with,
        "preferred": PREFERRED,
        "families": rows,
    }
    (a.out / "families.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    total = sum(r["count"] for r in rows)
    print(f"wrote {total} shapes in {len(rows)} families to {a.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
