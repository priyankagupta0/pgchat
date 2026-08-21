from __future__ import annotations

from typing import Callable

from rich.console import Console
from rich.panel import Panel

from pgchat.config import SafetyConfig
from pgchat.safety.classify import Classification

ApproveFn = Callable[[str, Classification, dict], bool]


def needs_approval(classification: Classification, safety: SafetyConfig) -> bool:
    if classification.blocked:
        return False  # blocked outright, not approved
    if classification.risk == "read" and safety.auto_approve_read:
        return False
    return classification.risk in safety.require_approval_for


def console_approve(
    tool: str,
    classification: Classification,
    args: dict,
    console: Console | None = None,
) -> bool:
    c = console or Console()
    preview = {k: (str(v)[:300] + "…" if len(str(v)) > 300 else v) for k, v in args.items()}
    c.print(
        Panel(
            f"[bold]Tool:[/bold] {tool}\n"
            f"[bold]Risk:[/bold] {classification.risk} — {classification.reason}\n"
            f"[bold]Args:[/bold] {preview}",
            title="Approval required",
            border_style="yellow",
        )
    )
    answer = c.input("[bold yellow]Approve this action?[/bold yellow] [y/N] ").strip().lower()
    return answer in {"y", "yes"}
