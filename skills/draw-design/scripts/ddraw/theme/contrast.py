"""The contrast contract (PRD §15.1 FR-081)."""

from __future__ import annotations

from ddraw.errors import Finding
from ddraw.theme import color
from ddraw.theme.model import Theme

TEXT_ROLES = ("ink", "muted", "soft", "link", "accent")


def check(theme: Theme) -> list[Finding]:
    findings: list[Finding] = []
    paper = theme.solid("paper")
    for role in TEXT_ROLES:
        fg = theme.solid(role)
        ratio = color.contrast(fg, paper)
        if ratio < 4.5:
            findings.append(
                Finding(
                    "LR-T007",
                    f"{role} {fg} is {ratio:.2f}:1 on paper {paper}; text needs 4.5:1",
                    pointer=f"/colors/{role}",
                    fix="darken the token, keeping its hue",
                )
            )
    accent_fill = theme.solid("accent", 0.85)
    strong = theme.solid("inkStrong")
    ratio = color.contrast(strong, accent_fill)
    if ratio < 4.5:
        findings.append(
            Finding(
                "LR-T007",
                f"inkStrong on accent fill is {ratio:.2f}:1; needs 4.5:1",
                pointer="/colors/inkStrong",
                severity="warn",
            )
        )
    return findings


def report(theme: Theme) -> list[tuple[str, float]]:
    paper = theme.solid("paper")
    return [(role, color.contrast(theme.solid(role), paper)) for role in TEXT_ROLES]
