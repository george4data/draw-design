"""draw.io Desktop CLI discovery and export (PRD §14, Appendix B.3)."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ddraw.errors import DDError, Finding

FORMATS = {
    "png": ("png", False),
    "svg": ("svg", False),
    "pdf": ("pdf", False),
    "jpg": ("jpg", False),
    "drawio.png": ("png", True),
    "drawio.svg": ("svg", True),
}
TIMEOUT = 120


@dataclass
class Cli:
    path: Path
    version: str
    wrapper: list[str]


def candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("DRAWIO_CLI")
    if env:
        out.append(Path(env))
    for name in ("drawio", "draw.io"):
        found = shutil.which(name)
        if found:
            out.append(Path(found))
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        out += [
            Path("/Applications/draw.io.app/Contents/MacOS/draw.io"),
            home / "Applications/draw.io.app/Contents/MacOS/draw.io",
        ]
    elif system == "Linux":
        out += [
            Path("/opt/drawio/drawio"),
            Path("/snap/bin/drawio"),
            Path("/mnt/c/Program Files/draw.io/draw.io.exe"),
        ]
    elif system == "Windows":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        la = os.environ.get("LOCALAPPDATA", "")
        out += [Path(pf) / "draw.io" / "draw.io.exe"]
        if la:
            out.append(Path(la) / "Programs" / "draw.io" / "draw.io.exe")
    return out


def _wrapper() -> list[str]:
    if platform.system() == "Linux" and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        return ["xvfb-run", "-a"]
    return []


def _extra_flags() -> list[str]:
    flags = ["--disable-update"]
    if platform.system() == "Linux" and (os.geteuid() == 0 if hasattr(os, "geteuid") else False):
        flags += ["--no-sandbox", "--disable-gpu"]
    return flags


def find() -> Cli | None:
    for c in candidates():
        if c.is_file() and os.access(c, os.X_OK):
            wrapper = _wrapper()
            try:
                proc = subprocess.run(
                    [*wrapper, str(c), "--version", *_extra_flags()],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            m = re.search(r"\d+\.\d+\.\d+", proc.stdout + proc.stderr)
            return Cli(c, m.group(0) if m else "unknown", wrapper)
    return None


def require() -> Cli:
    cli = find()
    if cli is None:
        raise DDError(
            [
                Finding(
                    "EXPORT-001",
                    "draw.io Desktop CLI not found",
                    fix="install draw.io Desktop (https://github.com/jgraph/drawio-desktop/releases) "
                    "or set DRAWIO_CLI to its executable",
                )
            ]
        )
    return cli


def free_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.name, ""
    for ext in (".drawio.png", ".drawio.svg", ".png", ".svg", ".pdf", ".jpg"):
        if path.name.endswith(ext):
            stem, suffix = path.name[: -len(ext)], ext
            break
    i = 1
    while True:
        cand = path.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


def default_output(src: Path, fmt: str) -> Path:
    stem = src.name[: -len(".drawio")] if src.name.endswith(".drawio") else src.stem
    return src.with_name(f"{stem}.{fmt}")


def export(
    src: Path,
    fmt: str,
    out: Path | None = None,
    *,
    scale: float = 2.0,
    page: int | None = None,
    all_pages: bool = False,
    transparent: bool = True,
    theme: str | None = None,
    timeout: int = TIMEOUT,
    cli: Cli | None = None,
) -> Path:
    if fmt not in FORMATS:
        raise DDError([Finding("EXPORT-002", f"unknown format {fmt!r}", fix=f"one of {', '.join(FORMATS)}")])
    if not 1.0 <= scale <= 4.0:
        raise DDError(
            [
                Finding(
                    "EXPORT-003",
                    f"scale {scale} outside 1–4",
                    fix="redraw at a different size preset instead of scaling below 1 or above 4",
                )
            ]
        )
    if not src.is_file():
        raise DDError([Finding("EXPORT-004", f"{src} does not exist")])
    cli = cli or require()
    kind, embed = FORMATS[fmt]
    target = out if out is not None else free_path(default_output(src, fmt))
    args = [*cli.wrapper, str(cli.path), "-x", "-f", kind, "-o", str(target)]
    if kind in ("png", "svg", "jpg"):
        args += ["-s", f"{scale:g}"]
    if transparent and kind in ("png", "svg"):
        args += ["-t"]
    if embed:
        args += ["-e"]
    if kind == "pdf":
        args += ["--crop"]
    if all_pages and kind in ("pdf", "svg"):
        args += ["-a"]
    elif page is not None:
        args += ["-p", str(page)]
    if theme in ("dark", "light"):
        args += ["--theme", theme]
    args += [*_extra_flags(), str(src)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DDError([Finding("EXPORT-005", f"draw.io export timed out after {timeout}s")]) from exc
    if proc.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        msg = (proc.stderr or proc.stdout).strip()[-800:]
        raise DDError([Finding("EXPORT-006", f"draw.io export failed: {msg or 'no output'}")])
    if kind == "svg":
        from ddraw.export.svg_post import add_accessibility

        add_accessibility(target, src)
    return target


def preview(src: Path, page: int | None = None, theme: str | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="ddraw-preview-"))
    stem = src.name[: -len(".drawio")] if src.name.endswith(".drawio") else src.stem
    return export(src, "png", tmp / f"{stem}.png", scale=1.0, page=page, transparent=False, theme=theme)
