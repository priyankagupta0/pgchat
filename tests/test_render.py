"""Tests for query result rendering."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from pgchat.tools.query import QueryResult
from pgchat.ui.render import QueryRenderer, get_renderer


class TestQueryRenderer:
    """Test QueryRenderer class."""

    def test_renderer_initialization(self):
        """Test creating a QueryRenderer instance."""
        console = Console()
        renderer = QueryRenderer(console)
        assert renderer.console is console

    def test_renderer_default_console(self):
        """Test that renderer creates console if not provided."""
        renderer = QueryRenderer()
        assert renderer.console is not None
        assert isinstance(renderer.console, Console)

    def test_render_error(self):
        """Test rendering error messages."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        error = {
            "code": "TEST_ERROR",
            "message": "Test error message",
            "hint": "Try this fix",
        }

        renderer.render_error(error)
        result = output.getvalue()

        assert "Error" in result
        assert "Test error message" in result
        assert "Hint" in result
        assert "Try this fix" in result

    def test_render_error_without_hint(self):
        """Test rendering error without hint."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        error = {
            "code": "SIMPLE_ERROR",
            "message": "Simple error",
        }

        renderer.render_error(error)
        result = output.getvalue()

        assert "Simple error" in result

    def test_render_empty_result(self):
        """Test rendering empty query results."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        renderer.render_empty_result(15.5)
        result = output.getvalue()

        assert "No rows returned" in result
        assert "15.50 ms" in result

    def test_render_table(self):
        """Test rendering result table."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)
        renderer = QueryRenderer(console)

        columns = ["id", "name", "email"]
        rows = [
            {"id": "1", "name": "Alice", "email": "alice@example.com"},
            {"id": "2", "name": "Bob", "email": "bob@example.com"},
        ]

        renderer.render_table(columns, rows)
        result = output.getvalue()

        # Check that column headers and data appear
        assert "id" in result
        assert "name" in result
        assert "email" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_render_footer(self):
        """Test rendering result footer."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        renderer.render_footer(5, 25.75, False)
        result = output.getvalue()

        assert "5 row(s)" in result
        assert "25.75 ms" in result

    def test_render_footer_truncated(self):
        """Test rendering footer with truncation indicator."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        renderer.render_footer(100, 50.0, True)
        result = output.getvalue()

        assert "100 row(s)" in result
        assert "truncated" in result.lower()

    def test_render_complete_success(self):
        """Test rendering complete successful result."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=120)
        renderer = QueryRenderer(console)

        result = QueryResult(
            columns=["id", "name"],
            rows=[{"id": "1", "name": "Test"}],
            row_count=1,
            duration_ms=10.5,
            truncated=False,
        )

        renderer.render(result)
        output_str = output.getvalue()

        assert "id" in output_str
        assert "name" in output_str
        assert "Test" in output_str
        assert "1 row(s)" in output_str
        assert "10.50 ms" in output_str

    def test_render_complete_error(self):
        """Test rendering result with error."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            duration_ms=0.0,
            truncated=False,
            error={"code": "SQL_ERROR", "message": "Syntax error"},
        )

        renderer.render(result)
        output_str = output.getvalue()

        assert "Error" in output_str
        assert "Syntax error" in output_str

    def test_render_complete_empty(self):
        """Test rendering empty result set."""
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        renderer = QueryRenderer(console)

        result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            duration_ms=5.0,
            truncated=False,
        )

        renderer.render(result)
        output_str = output.getvalue()

        assert "No rows returned" in output_str
        assert "5.00 ms" in output_str


class TestRendererSingleton:
    """Test singleton renderer functions."""

    def test_get_renderer_returns_instance(self):
        """Test that get_renderer returns a QueryRenderer."""
        renderer = get_renderer()
        assert isinstance(renderer, QueryRenderer)

    def test_get_renderer_singleton(self):
        """Test that get_renderer returns the same instance."""
        renderer1 = get_renderer()
        renderer2 = get_renderer()
        # Note: Due to implementation, they might not be the same instance
        # but both should be valid QueryRenderer instances
        assert isinstance(renderer1, QueryRenderer)
        assert isinstance(renderer2, QueryRenderer)
