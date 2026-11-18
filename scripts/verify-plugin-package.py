#!/usr/bin/env python3
"""Verify the plugin package: manifests agree, every shipped type is complete, SKILL.md fits its budget."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "draw-design"
sys.path.insert(0, str(SKILL / "scripts"))

from ddraw import registry  # noqa: E402

SKILL_MD_MAX = 32 * 1024
TYPE_REF_MAX = 12 * 1024


def main() -> int:
    errors: list[str] = []
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    for key in ("name", "description", "version", "keywords", "license"):
        if claude.get(key) != codex.get(key):
            errors.append(f"manifest field {key!r} differs between Claude and Codex")
    if codex.get("skills") != "./skills/":
        errors.append("codex manifest must point skills at ./skills/")
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if len(skill_md.encode()) > SKILL_MD_MAX:
        errors.append(f"SKILL.md is {len(skill_md.encode())} bytes (max {SKILL_MD_MAX})")
    m = re.match(r"---\nname: ([^\n]+)\ndescription: ([^\n]+)\n", skill_md)
    if not m or m.group(1) != "draw-design":
        errors.append("SKILL.md frontmatter must start with name: draw-design and a description")
    for t in registry.shipped():
        ref = SKILL / "references" / f"type-{t.slug}.md"
        ex = SKILL / "examples" / f"{t.slug}.dd.json"
        golden = ROOT / "tests" / "golden" / f"{t.slug}.drawio"
        for path in (ref, ex, golden):
            if not path.is_file():
                errors.append(f"shipped type {t.slug}: missing {path.relative_to(ROOT)}")
        if ref.is_file() and len(ref.read_bytes()) > TYPE_REF_MAX:
            errors.append(f"{ref.name} exceeds {TYPE_REF_MAX} bytes")
        if t.slug not in skill_md:
            errors.append(f"SKILL.md does not mention shipped type {t.slug}")
    for cmd in sorted((ROOT / "commands").glob("*.md")):
        text = cmd.read_text(encoding="utf-8")
        if not text.startswith("---\ndescription: "):
            errors.append(f"{cmd.name}: missing description frontmatter")
        for ref in re.findall(r"references/([a-z0-9-]+\.md)", text):
            if not (SKILL / "references" / ref).is_file():
                errors.append(f"{cmd.name}: references missing file {ref}")
    for ref in re.findall(r"\]\((references/[^)]+)\)", skill_md):
        if not (SKILL / ref).is_file():
            errors.append(f"SKILL.md links to missing {ref}")
    if errors:
        print("package verification failed:", *errors, sep="\n  ")
        return 1
    print(f"package OK: {len(registry.shipped())} shipped types, SKILL.md {len(skill_md.encode())} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
