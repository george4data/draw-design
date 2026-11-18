"""`ddraw` command line (PRD §17.1). Machine output on stdout with --json, human text on stderr."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ddraw import __version__, registry
from ddraw.errors import DDError, Finding
from ddraw.paths import EXAMPLES_DIR, SCHEMAS_DIR

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _report(
    findings: list[Finding], as_json: bool, extra: dict[str, Any] | None = None, strict: bool = False
) -> int:
    errors = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity == "warn"]
    status = "error" if errors or (strict and warns) else ("warn" if warns else "ok")
    if as_json:
        payload = {"status": status, "findings": [f.to_dict() for f in findings], **(extra or {})}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            if f.severity != "info":
                _err(f.human())
        if extra and extra.get("output"):
            _err(f"wrote {extra['output']}")
        _err(f"{len(errors)} error(s), {len(warns)} warning(s)")
    return EXIT_FINDINGS if status == "error" else EXIT_OK


def cmd_build(a: argparse.Namespace) -> int:
    from ddraw.pipeline import build
    from ddraw.spec.validate import load_json

    src = Path(a.spec)
    data = load_json(src)
    project = Path(a.project) if a.project else src.resolve().parent
    result = build(
        data,
        project=project,
        theme_path=Path(a.theme) if a.theme else None,
        profile=a.profile,
        adaptive=not a.no_adaptive,
        run_lint=not a.no_lint,
    )
    out = (
        Path(a.output)
        if a.output
        else src.with_name(src.name.replace(".dd.json", "").replace(".json", "") + ".drawio")
    )
    stats = {
        "nodes": len(result.page.nodes),
        "edges": len(result.page.edges),
        "zones": len(result.page.zones),
        "size": f"{result.page.frame.w:.0f}x{result.page.frame.h:.0f}",
        "theme": result.theme.slug,
    }
    if result.ok or a.force:
        out.write_text(result.xml, encoding="utf-8")
        return _report(result.findings, a.json, {"output": str(out), "stats": stats}, a.strict)
    _err(f"not written: fix the errors (or pass --force to write {out} anyway)")
    return _report(result.findings, a.json, {"stats": stats})


def cmd_validate(a: argparse.Namespace) -> int:
    from ddraw.spec.validate import load_json, validate

    _, findings = validate(load_json(Path(a.spec)))
    return _report(findings, a.json)


def cmd_new(a: argparse.Namespace) -> int:
    info = registry.types().get(a.type)
    if info is None:
        _err(f"unknown type {a.type!r}; run: ddraw types")
        return EXIT_USAGE
    src = EXAMPLES_DIR / f"{a.type}.dd.json"
    if info.status != "shipped" or not src.is_file():
        _err(f"type {a.type!r} is {info.status}; shipped: {', '.join(t.slug for t in registry.shipped())}")
        return EXIT_USAGE
    out = Path(a.output or f"{a.type}.dd.json")
    if out.exists() and not a.force:
        _err(f"{out} exists; pass --force to overwrite")
        return EXIT_USAGE
    shutil.copyfile(src, out)
    _err(f"wrote {out}")
    return EXIT_OK


def cmd_types(a: argparse.Namespace) -> int:
    items = [t for t in registry.types().values() if a.all or t.status == "shipped"]
    if a.json:
        print(json.dumps([t.to_dict() for t in items], indent=2))
    else:
        for t in items:
            print(f"{t.slug:26} {t.status:9} {t.family:11} {t.use_when or t.name}")
    return EXIT_OK


def cmd_schema(a: argparse.Namespace) -> int:
    path = SCHEMAS_DIR / f"{a.which}.schema.json"
    if not path.is_file():
        _err(f"no schema {a.which!r}")
        return EXIT_USAGE
    print(path.read_text(encoding="utf-8"))
    return EXIT_OK


def cmd_lint(a: argparse.Namespace) -> int:
    from ddraw.lint.runner import lint_file
    from ddraw.theme.model import load_theme
    from ddraw.theme.resolve import profile_path

    theme = None
    if a.profile:
        p = None if a.profile == "default" else profile_path(a.profile)
        theme = load_theme(p)
    only = a.rules.split(",") if a.rules else None
    findings = lint_file(Path(a.file), theme, only)
    return _report(findings, a.json, {"file": a.file}, a.strict)


def cmd_export(a: argparse.Namespace) -> int:
    from ddraw.export.drawio_cli import export

    out = export(
        Path(a.file),
        a.format,
        Path(a.output) if a.output else None,
        scale=a.scale,
        page=a.page,
        all_pages=a.all_pages,
        transparent=not a.opaque,
        theme=a.theme,
    )
    if a.json:
        print(json.dumps({"status": "ok", "output": str(out)}))
    else:
        _err(f"wrote {out}")
    return EXIT_OK


def cmd_preview(a: argparse.Namespace) -> int:
    from ddraw.export.drawio_cli import preview

    out = preview(Path(a.file), a.page, a.theme)
    print(str(out))
    return EXIT_OK


def cmd_doctor(a: argparse.Namespace) -> int:
    from ddraw import doctor

    text, code = doctor.render(doctor.run(Path(a.project or ".")), a.json, a.strict)
    print(text)
    return code


def cmd_theme(a: argparse.Namespace) -> int:
    from ddraw.theme.contrast import check, report
    from ddraw.theme.model import load_theme
    from ddraw.theme.resolve import resolve

    if a.action == "resolve":
        res = resolve(Path(a.project or "."))
        if a.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(f"{res.status} {res.slug} {res.path or ''}".strip())
            for note in res.notes:
                _err(note)
        return EXIT_OK
    theme = load_theme(Path(a.path) if a.path else None)
    if a.action == "check":
        findings = check(theme)
        if not a.json:
            for skin, role, ratio in report(theme):
                _err(f"{skin:5} {role:7} {ratio:5.2f}:1")
        return _report(findings, a.json)
    print(json.dumps(theme.raw, indent=2))
    return EXIT_OK


def cmd_profile(a: argparse.Namespace) -> int:
    from ddraw.theme import profiles

    verb = a.verb
    if verb == "list":
        items = profiles.list_profiles()
        if a.json:
            print(json.dumps(items, indent=2))
        elif not items:
            _err("no saved profiles yet (create one with: ddraw profile new <slug> --name <Name>)")
        else:
            for p in items:
                print(
                    f"{p['slug']:20} {p.get('name', ''):24} {p.get('updated', ''):10} {p.get('status', '')}"
                )
        return EXIT_OK
    if not a.slug:
        _err(f"`ddraw profile {verb}` needs a slug")
        return EXIT_USAGE
    if verb == "new":
        path, findings = profiles.create(
            a.slug,
            a.name or a.slug,
            source=Path(a.source) if a.source else None,
            source_url=a.source_url or "",
            notes=a.notes or "",
            force=a.force,
        )
        _err(f"wrote {path}")
        return _report(findings, a.json, {"output": str(path)})
    if verb == "show":
        print(json.dumps(profiles.show(a.slug), indent=2))
        return EXIT_OK
    if verb == "use":
        marker = profiles.use(a.slug, Path(a.project or "."))
        _err(f"wrote {marker} (profile: {a.slug})")
        return EXIT_OK
    if verb == "load":
        _err(f"active theme: {profiles.load(a.slug)}")
        return EXIT_OK
    if verb == "reset":
        _err(f"active theme: {profiles.reset()}")
        return EXIT_OK
    if verb == "delete":
        if not a.yes:
            _err("deleting a profile cannot be undone: confirm with the user, then pass --yes")
            return EXIT_USAGE
        _err(f"deleted {profiles.delete(a.slug)}")
        return EXIT_OK
    _err(f"unknown verb {verb!r}")
    return EXIT_USAGE


def cmd_import(a: argparse.Namespace) -> int:
    from ddraw.importers.restyle import restyle_file
    from ddraw.pipeline import resolve_theme_for

    src = Path(a.src)
    if a.mode != "restyle":
        _err("redraw import is planned; use --mode restyle to keep the layout and apply the theme")
        return EXIT_USAGE
    if not src.name.endswith((".drawio", ".xml", ".dio")):
        _err("restyle supports .drawio / .xml files (Mermaid, PlantUML and Excalidraw redraw are planned)")
        return EXIT_USAGE
    theme = resolve_theme_for(Path(a.project) if a.project else src.resolve().parent, a.profile)
    focal = set(a.focal.split(",")) if a.focal else set()
    out, report = restyle_file(
        src,
        Path(a.output) if a.output else None,
        theme,
        snap=a.snap,
        focal=focal,
        orthogonal=not a.keep_edges,
    )
    text = report.markdown(str(src), str(out))
    if a.json:
        print(json.dumps({"status": "ok", "output": str(out), "report": text}))
    else:
        print(text)
    return EXIT_OK


def not_implemented(name: str) -> Callable[[argparse.Namespace], int]:
    def run(_: argparse.Namespace) -> int:
        _err(f"`ddraw {name}` is not implemented yet (see docs/prd.md §22 for its milestone)")
        return EXIT_USAGE

    return run


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ddraw", description="Compile Diagram Specs into editorial draw.io files."
    )
    p.add_argument("--version", action="version", version=f"ddraw {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="validate, compile and lint a spec into a .drawio file")
    b.add_argument("spec")
    b.add_argument("-o", "--output")
    b.add_argument("--profile")
    b.add_argument("--theme", help="path to a theme JSON file")
    b.add_argument("--project", help="project root for marker/profile resolution (default: spec directory)")
    b.add_argument("--no-adaptive", action="store_true", help="plain colours instead of light-dark()")
    b.add_argument("--no-lint", action="store_true")
    b.add_argument("--force", action="store_true", help="write the file even when lint reports errors")
    b.add_argument("--strict", action="store_true")
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=cmd_build)

    v = sub.add_parser("validate", help="validate a spec without compiling")
    v.add_argument("spec")
    v.add_argument("--json", action="store_true")
    v.set_defaults(fn=cmd_validate)

    n = sub.add_parser("new", help="scaffold a spec from a type's canonical example")
    n.add_argument("type")
    n.add_argument("-o", "--output")
    n.add_argument("--force", action="store_true")
    n.set_defaults(fn=cmd_new)

    t = sub.add_parser("types", help="list diagram types")
    t.add_argument("--all", action="store_true", help="include planned types")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_types)

    s = sub.add_parser("schema", help="print a JSON Schema")
    s.add_argument("which", nargs="?", default="spec")
    s.set_defaults(fn=cmd_schema)

    li = sub.add_parser("lint", help="lint a .drawio file")
    li.add_argument("file")
    li.add_argument("--profile")
    li.add_argument("--rules", help="comma-separated rule prefixes, e.g. LR-C,LR-G001")
    li.add_argument("--strict", action="store_true")
    li.add_argument("--json", action="store_true")
    li.set_defaults(fn=cmd_lint)

    e = sub.add_parser(
        "export", help="export via draw.io Desktop (png, svg, pdf, jpg, drawio.png, drawio.svg)"
    )
    e.add_argument("file")
    e.add_argument("--format", default="png")
    e.add_argument("-o", "--output")
    e.add_argument("--scale", type=float, default=2.0)
    e.add_argument("--page", type=int, help="1-based page index")
    e.add_argument("--all-pages", action="store_true")
    e.add_argument("--opaque", action="store_true", help="keep the background (no -t)")
    e.add_argument("--theme", choices=["light", "dark"])
    e.add_argument("--json", action="store_true")
    e.set_defaults(fn=cmd_export)

    pv = sub.add_parser("preview", help="render a temporary PNG for visual review; prints its path")
    pv.add_argument("file")
    pv.add_argument("--page", type=int)
    pv.add_argument("--theme", choices=["light", "dark"])
    pv.set_defaults(fn=cmd_preview)

    d = sub.add_parser("doctor", help="environment diagnostics")
    d.add_argument("--project")
    d.add_argument("--strict", action="store_true")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_doctor)

    th = sub.add_parser("theme", help="theme operations")
    th.add_argument("action", choices=["resolve", "check", "show"])
    th.add_argument("path", nargs="?", help="theme JSON (check/show); default theme when omitted")
    th.add_argument("--project")
    th.add_argument("--json", action="store_true")
    th.set_defaults(fn=cmd_theme)

    pr = sub.add_parser("profile", help="client profiles in ~/.draw-design/profiles")
    pr.add_argument("verb", choices=["list", "new", "show", "use", "load", "reset", "delete"])
    pr.add_argument("slug", nargs="?")
    pr.add_argument("--name")
    pr.add_argument("--source", help="theme JSON to copy (default: the shipped default theme)")
    pr.add_argument("--source-url")
    pr.add_argument("--notes")
    pr.add_argument("--project", help="project root for `use` (default: current directory)")
    pr.add_argument("--force", action="store_true", help="overwrite an existing profile (`new`)")
    pr.add_argument("--yes", action="store_true", help="confirm `delete`")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(fn=cmd_profile)

    im = sub.add_parser("import", help="restyle an existing draw.io file to the theme (redraw planned)")
    im.add_argument("src")
    im.add_argument("--mode", choices=["restyle", "redraw"], default="restyle")
    im.add_argument("-o", "--output")
    im.add_argument("--snap", action="store_true", help="snap shapes to the 4px grid")
    im.add_argument("--focal", help="comma-separated cell ids to accent (max 2)")
    im.add_argument("--keep-edges", action="store_true", help="keep the source edge routing style")
    im.add_argument("--profile")
    im.add_argument("--project")
    im.add_argument("--json", action="store_true")
    im.set_defaults(fn=cmd_import)

    for name, helptext in (
        ("digest", "import digest"),
        ("icons", "icon catalog"),
        ("library", "brand library"),
        ("sync", "round-trip edits"),
        ("registry", "block registry"),
    ):
        x = sub.add_parser(name, help=f"{helptext} (planned)")
        x.add_argument("args", nargs="*")
        x.set_defaults(fn=not_implemented(name))
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        code: int = args.fn(args)
        return code
    except DDError as exc:
        as_json = bool(getattr(args, "json", False))
        if as_json:
            print(
                json.dumps(
                    {"status": "error", "findings": [f.to_dict() for f in exc.findings]},
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            for f in exc.findings:
                _err(f.human())
        codes = {f.code for f in exc.findings}
        if codes & {"EXPORT-001"}:
            return EXIT_ENV
        usage = ("SPEC", "EXPORT", "THEME", "PROFILE")
        return EXIT_USAGE if any(c.startswith(usage) for c in codes) else EXIT_FINDINGS
