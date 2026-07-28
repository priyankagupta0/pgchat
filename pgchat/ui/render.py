"""Rich-based terminal UI rendering for pgchat query results."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from pgchat.tools.query import QueryResult


class QueryRenderer:
    """Handles rendering of query results to the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        """
        Initialize the query renderer.

        Args:
            console: Optional Rich Console instance. Creates a new one if not provided.
        """
        self.console = console or Console()

    def render_error(self, error: dict[str, str]) -> None:
        """
        Render an error message.

        Args:
            error: Dictionary containing 'message' and optionally 'hint' and 'code'.
        """
        message = error.get("message", "Unknown error")
        self.console.print(f"[red]Error:[/red] {message}")

        if hint := error.get("hint"):
            self.console.print(f"[yellow]Hint:[/yellow] {hint}")

        if code := error.get("code"):
            self.console.print(f"[dim]Code: {code}[/dim]")

    def render_empty_result(self, duration_ms: float) -> None:
        """
        Render an empty result message.

        Args:
            duration_ms: Query execution time in milliseconds.
        """
        self.console.print("[dim]No rows returned.[/dim]")
        self.console.print(f"[dim]{duration_ms:.2f} ms[/dim]")

    def render_table(
        self, columns: list[str], rows: list[dict[str, Any]], max_col_width: int = 50
    ) -> None:
        """
        Render a result table.

        Args:
            columns: List of column names.
            rows: List of row dictionaries.
            max_col_width: Maximum width for each column (default: 50).
        """
        table = Table(
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )

        for column in columns:
            table.add_column(str(column), overflow="fold", max_width=max_col_width)

        for row in rows:
            table.add_row(*(str(row.get(col, "")) for col in columns))

        self.console.print(table)

    def render_footer(
        self, row_count: int, duration_ms: float, truncated: bool
    ) -> None:
        """
        Render result footer with metadata.

        Args:
            row_count: Number of rows returned.
            duration_ms: Query execution time in milliseconds.
            truncated: Whether results were truncated.
        """
        footer = f"{row_count} row(s) in {duration_ms:.2f} ms"
        if truncated:
            footer += " [yellow][truncated][/yellow]"
        self.console.print(f"[dim]{footer}[/dim]")

    def render(self, result: QueryResult) -> None:
        """
        Render a complete query result.

        Args:
            result: QueryResult model containing query execution results.
        """
        if result.error:
            self.render_error(result.error)
            return

        if not result.rows:
            self.render_empty_result(result.duration_ms)
            return

        self.render_table(result.columns, result.rows)
        self.render_footer(result.row_count, result.duration_ms, result.truncated)


# Singleton instance for convenience
_default_renderer: QueryRenderer | None = None


def get_renderer() -> QueryRenderer:
    """Get or create the default renderer instance."""
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = QueryRenderer()
    return _default_renderer


def render_query_result(result: QueryResult) -> None:
    """
    Convenience function to render a query result using the default renderer.

    Args:
        result: QueryResult model containing query execution results.
    """
    get_renderer().render(result)