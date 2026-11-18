#!/usr/bin/env python3
"""Compile every example spec into gallery/<slug>.drawio (light and dark); --render also exports PNGs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "draw-design"
sys.path.insert(0, str(SKILL / "scripts"))

from ddraw.export import drawio_cli  # noqa: E402
from ddraw.pipeline import build  # noqa: E402


def main() -> int:
    render = "--render" in sys.argv
    out = ROOT / "gallery"
    out.mkdir(exist_ok=True)
    cli = drawio_cli.find() if render else None
    if render and cli is None:
        print("draw.io Desktop not found; set DRAWIO_CLI", file=sys.stderr)
        return 3
    failures = 0
    for spec_path in sorted((SKILL / "examples").glob("*.dd.json")):
        slug = spec_path.name[: -len(".dd.json")]
        for variant in ("light", "dark"):
            data = json.loads(spec_path.read_text(encoding="utf-8"))
            data["variant"] = variant
            result = build(data)
            name = slug if variant == "light" else f"{slug}-dark"
            target = out / f"{name}.drawio"
            target.write_text(result.xml, encoding="utf-8")
            errors = [f for f in result.findings if f.severity == "error"]
            failures += bool(errors)
            print(f"{'FAIL' if errors else 'ok  '} {target.relative_to(ROOT)}")
            if render and cli is not None:
                (out / "png").mkdir(exist_ok=True)
                png = drawio_cli.export(
                    target,
                    "png",
                    out / "png" / f"{name}.png",
                    scale=2,
                    transparent=False,
                    cli=cli,
                )
                print(f"     {png.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
