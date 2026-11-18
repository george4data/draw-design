"""The contrast contract (PRD §15.1 FR-081)."""

from __future__ import annotations

from ddraw.errors import Finding
from ddraw.theme import color
from ddraw.theme.model import Theme

TEXT_ROLES = ("ink", "muted", "soft", "link", "accent")


def check(theme: Theme) -> list[Finding]:
    findings: list[Finding] = []
    for skin in ("light", "dark"):
        paper = theme.solid(skin, "paper")
        for role in TEXT_ROLES:
            fg = theme.solid(skin, role)
            ratio = color.contrast(fg, paper)
            if ratio < 4.5:
                findings.append(
                    Finding(
                        "LR-T007",
                        f"{skin} {role} {fg} is {ratio:.2f}:1 on paper {paper}; text needs 4.5:1",
                        pointer=f"/{skin}/{role}",
                        fix="darken (light skin) or lighten (dark skin) the token, keeping its hue",
                    )
                )
        accent_fill = theme.solid(skin, "accent", 0.85)
        strong = theme.solid(skin, "inkStrong")
        ratio = color.contrast(strong, accent_fill)
        if ratio < 4.5:
            findings.append(
                Finding(
                    "LR-T007",
                    f"{skin} inkStrong on accent fill is {ratio:.2f}:1; needs 4.5:1",
                    pointer=f"/{skin}/inkStrong",
                    severity="warn",
                )
            )
    return findings


def report(theme: Theme) -> list[tuple[str, str, float]]:
    rows = []
    for skin in ("light", "dark"):
        paper = theme.solid(skin, "paper")
        for role in TEXT_ROLES:
            rows.append((skin, role, color.contrast(theme.solid(skin, role), paper)))
    return rows
