from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


def print_banner() -> None:
    console.print(
        Panel(
            "[bold]pgchat[/bold] — MCP-powered natural language database operator\n"
            "Talk to Postgres. Monitor, optimize, migrate, heal — with approvals.",
            border_style="cyan",
        )
    )


def print_user(text: str) -> None:
    console.print(f"\n[bold cyan]You[/bold cyan]: {text}")


def print_assistant(text: str) -> None:
    console.print("\n[bold green]pgchat[/bold green]:")
    console.print(Markdown(text))


def print_reasoning(text: str) -> None:
    if not text.strip():
        return
    console.print(Panel(text.strip(), title="Reasoning", border_style="dim", expand=False))


def print_tool_call(name: str, args: dict[str, Any]) -> None:
    preview = json.dumps(args, indent=2, default=str)
    if len(preview) > 1200:
        preview = preview[:1200] + "\n…"
    body = Syntax(preview, "json", theme="monokai", word_wrap=True)
    console.print(Panel(body, title=f"Tool → {name}", border_style="blue"))


def print_tool_result(name: str, result: str) -> None:
    text = result if len(result) < 2000 else result[:2000] + "\n…"
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "rows" in data and isinstance(data["rows"], list):
            _print_rows(data)
            return
    except (json.JSONDecodeError, TypeError):
        pass
    console.print(Panel(text, title=f"Result ← {name}", border_style="magenta"))


def _print_rows(data: dict[str, Any]) -> None:
    rows = data.get("rows") or []
    table = Table(title=f"Rows ({data.get('row_count', len(rows))})", show_lines=False)
    if not rows:
        console.print("[dim]No rows returned.[/dim]")
        return
    for key in rows[0].keys():
        table.add_column(str(key), overflow="fold")
    for row in rows[:50]:
        table.add_row(*[str(row.get(k, "")) for k in rows[0].keys()])
    console.print(table)
    if data.get("truncated"):
        console.print("[yellow]Results truncated by safety max_rows.[/yellow]")


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_info(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")
