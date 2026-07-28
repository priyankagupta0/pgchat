"""Command-line interface for PgChat - Natural language Postgres database operations."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console

from pgchat.agent.gemini_agent import run_chat
from pgchat.config import CONFIG_DIR, CONFIG_FILE, Settings, write_default_config
from pgchat.db.pool import Database
from pgchat.logging_config import get_logger, setup_logging

logger = get_logger(__name__)

# Typer app instance
app = typer.Typer(
    name="pgchat",
    help="Natural language Postgres database operator powered by Gemini and MCP.",
    add_completion=False,
)

console = Console()


@app.command()
def init() -> None:
    """
    Create a default pgchat configuration file.

    Generates a config file at ~/.pgchat/config.toml with template values
    for Gemini API key and Postgres connection string.

    You must edit this file and add your actual credentials before using pgchat.
    """
    try:
        write_default_config()

        if CONFIG_FILE.exists():
            console.print(f"[green]✓ Config file created:[/green] {CONFIG_FILE}")
            console.print("\n[bold]Next steps:[/bold]")
            console.print("1. Get a Gemini API key from https://aistudio.google.com/apikey")
            console.print(f"2. Edit [cyan]{CONFIG_FILE}[/cyan] and add your:")
            console.print("   • Gemini API key")
            console.print("   • Postgres database URL")
            console.print("3. Run [bold cyan]pgchat doctor[/bold cyan] to validate")
            console.print("4. Run [bold cyan]pgchat chat[/bold cyan] to start chatting")
        else:
            console.print(f"[yellow]Config file already exists:[/yellow] {CONFIG_FILE}")
            console.print("Edit it to update your settings.")

    except Exception as e:
        logger.exception("Failed to create config file")
        console.print(f"[red]✗ Error:[/red] Failed to create config file: {e}")
        raise typer.Exit(code=1)


@app.command()
def chat() -> None:
    """
    Start an interactive chat session with your Postgres database.

    Launches a natural language interface where you can ask questions about
    your database, explore schemas, and run read-only queries using plain English.

    Examples:
        pgchat chat
    """

    async def _run_chat() -> None:
        """Async wrapper for chat session."""
        try:
            settings = Settings.load()
        except ValidationError as e:
            console.print("[red]✗ Configuration error:[/red]")
            for error in e.errors():
                field = " → ".join(str(x) for x in error["loc"])
                console.print(f"  • {field}: {error['msg']}")
            console.print(f"\n[dim]Edit {CONFIG_FILE} or set environment variables.[/dim]")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[red]✗ Error loading settings:[/red] {e}")
            console.print(f"[dim]Run [bold]pgchat init[/bold] to create {CONFIG_FILE}[/dim]")
            raise typer.Exit(code=1)

        try:
            await Database.init(settings)
            logger.info("Database pool initialized")
        except Exception as e:
            console.print(f"[red]✗ Database connection failed:[/red] {e}")
            console.print("\n[yellow]Troubleshooting:[/yellow]")
            console.print("• Check your database URL in the config file")
            console.print("• Ensure Postgres is running and accessible")
            console.print("• Verify credentials and permissions")
            raise typer.Exit(code=1)

        try:
            await run_chat(settings)
        except KeyboardInterrupt:
            console.print("\n[dim]Chat interrupted[/dim]")
        except Exception as e:
            logger.exception("Chat session failed")
            console.print(f"\n[red]✗ Chat error:[/red] {e}")
        finally:
            await Database.close()
            logger.info("Database pool closed")

    try:
        asyncio.run(_run_chat())
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Fatal error in chat command")
        console.print(f"[red]✗ Fatal error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def mcp() -> None:
    """
    Start the PgChat MCP (Model Context Protocol) server.

    Launches an MCP server that communicates via stdio, allowing AI assistants
    and other MCP clients to interact with your Postgres database using
    natural language and structured queries.

    The server runs until terminated with Ctrl+C.

    Examples:
        pgchat mcp
    """
    console.print("[cyan]Starting PgChat MCP server...[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pgchat.mcp_server.server"],
            check=False,
        )

        if result.returncode != 0 and result.returncode != -2:  # -2 is SIGINT
            console.print(f"[yellow]Server exited with code {result.returncode}[/yellow]")
            raise typer.Exit(code=result.returncode)

    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped[/dim]")
    except FileNotFoundError:
        console.print("[red]✗ Error:[/red] Python executable not found")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception("MCP server failed")
        console.print(f"[red]✗ MCP server error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """
    Validate PgChat configuration and environment.

    Checks that all required settings are properly configured:
    • Gemini API key is set and valid
    • Database URL is properly formatted
    • Configuration file exists and is readable

    Returns exit code 0 if all checks pass, 1 if any fail.

    Examples:
        pgchat doctor
    """
    console.print("[bold cyan]PgChat Configuration Check[/bold cyan]\n")

    all_ok = True

    # Check if config file exists
    if CONFIG_FILE.exists():
        console.print(f"[green]✓[/green] Config file: {CONFIG_FILE}")
    else:
        console.print(f"[red]✗[/red] Config file not found: {CONFIG_FILE}")
        console.print(f"  [dim]Run [bold]pgchat init[/bold] to create it[/dim]")
        all_ok = False

    # Try to load settings
    try:
        settings = Settings.load()
    except ValidationError as e:
        console.print("\n[red]✗ Configuration validation failed:[/red]")
        for error in e.errors():
            field = " → ".join(str(x) for x in error["loc"])
            console.print(f"  • {field}: {error['msg']}")
        all_ok = False
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]✗ Error loading settings:[/red] {e}")
        all_ok = False
        raise typer.Exit(code=1)

    # Check Gemini API key
    if settings.gemini_api_key and "PASTE_" not in settings.gemini_api_key:
        console.print("[green]✓[/green] Gemini API key configured")
    else:
        console.print("[red]✗[/red] Gemini API key missing or invalid")
        console.print("  [dim]Get one from https://aistudio.google.com/apikey[/dim]")
        all_ok = False

    # Check database URL
    if settings.database_url:
        # Hide password in output
        from urllib.parse import urlparse
        _parsed = urlparse(str(settings.database_url))
        safe_url = str(settings.database_url).replace(
            f":{_parsed.password}@", ":***@"
        ) if _parsed.password else str(settings.database_url)
        console.print(f"[green]✓[/green] Database URL: {safe_url}")
    else:
        console.print("[red]✗[/red] Database URL missing or invalid")
        console.print("  [dim]Format: postgresql://user:pass@host:port/dbname[/dim]")
        all_ok = False

    # Display other settings
    console.print(f"\n[bold]Settings:[/bold]")
    console.print(f"  • Model: {settings.gemini_model}")
    console.print(f"  • Query limit: {settings.query_limit} rows")
    console.print(f"  • Statement timeout: {settings.statement_timeout_ms} ms")
    console.print(f"  • Pool size: {settings.pool_min_size}-{settings.pool_max_size} connections")

    # Final verdict
    if all_ok:
        console.print("\n[bold green]All checks passed! ✓[/bold green]")
        console.print("[dim]You're ready to run [bold]pgchat chat[/bold][/dim]")
    else:
        console.print("\n[bold red]Some checks failed ✗[/bold red]")
        console.print(f"[dim]Edit {CONFIG_FILE} to fix the issues[/dim]")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """
    Display PgChat version information.
    """
    from pgchat import __version__

    console.print(f"[bold]PgChat[/bold] version [cyan]{__version__}[/cyan]")
    console.print("[dim]Natural language Postgres database operator[/dim]")


def main() -> None:
    """Main entry point for the CLI application."""
    # Setup logging for CLI (warnings only to keep console clean)
    setup_logging(console_level="WARNING", enable_file=True)
    app()