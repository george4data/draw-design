"""Structured findings shared by validation, layout, routing and lint."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Finding:
    code: str
    message: str
    severity: str = "error"
    pointer: str | None = None
    cell: str | None = None
    fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def human(self) -> str:
        where = self.pointer or self.cell or ""
        loc = f" [{where}]" if where else ""
        fix = f"\n    fix: {self.fix}" if self.fix else ""
        return f"{self.severity.upper()} {self.code}{loc}: {self.message}{fix}"


@dataclass
class DDError(Exception):
    """Raised when a stage cannot continue. Carries one or more findings."""

    findings: list[Finding] = field(default_factory=list)

    def __str__(self) -> str:
        return "\n".join(f.human() for f in self.findings)


def fail(code: str, message: str, *, pointer: str | None = None, fix: str | None = None) -> DDError:
    return DDError([Finding(code, message, "error", pointer=pointer, fix=fix)])
