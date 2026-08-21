from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.prompt import Confirm, Prompt

from pgchat.config import Config, DatabaseConfig, GeminiConfig, SafetyConfig, load_config, save_config
from pgchat.ui import render

app = typer.Typer(
    name="pgchat",
    help="pgchat — MCP-powered natural language PostgreSQL operator.",
    no_args_is_help=True,
)


@app.command()
def init(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Write defaults without prompts."
    ),
) -> None:
    """Create ~/.pgchat/config.toml with database and Gemini settings."""
    if non_interactive:
        path = save_config(Config())
        render.print_info(f"Wrote default config to {path}")
        return

    render.print_banner()
    render.console.print("Configure Postgres connection and Gemini API key.\n")

    host = Prompt.ask("Database host", default="localhost")
    port = int(Prompt.ask("Database port", default="5432"))
    user = Prompt.ask("Database user", default="postgres")
    password = Prompt.ask("Database password", password=True, default="")
    database = Prompt.ask("Database name", default="postgres")
    api_key = Prompt.ask("Gemini API key", password=True, default="")
    model = Prompt.ask("Gemini model", default="gemini-2.0-flash")

    require_approval = Confirm.ask(
        "Require approval for write/DDL/admin actions?", default=True
    )
    safety = SafetyConfig(
        require_approval_for=["write", "ddl", "destructive", "admin"]
        if require_approval
        else [],
        auto_approve_read=True,
    )

    config = Config(
        database=DatabaseConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        ),
        gemini=GeminiConfig(api_key=api_key, model=model),
        safety=safety,
    )
    path = save_config(config)
    render.console.print(f"[green]Saved config to {path}[/green]")


@app.command()
def chat(
    query: Optional[str] = typer.Argument(
        None, help="One-shot question (omit for interactive REPL)."
    ),
) -> None:
    """Chat with your database via Gemini + local MCP tools."""
    try:
        config = load_config()
    except FileNotFoundError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=1) from exc

    from pgchat.agent.gemini_agent import GeminiAgent

    agent = GeminiAgent(config)

    async def _run() -> None:
        if query:
            answer = await agent.ask_once(query)
            render.print_assistant(answer or "(no response)")
        else:
            await agent.run_session()

    asyncio.run(_run())


@app.command()
def mcp() -> None:
    """Run the pgchat MCP server on stdio (for Cursor / Claude Desktop / agents)."""
    from pgchat.mcp_server.server import main

    main()


@app.command("tools")
def list_tools() -> None:
    """List built-in MCP tool names."""
    from pgchat.tools import TOOL_HANDLERS

    for name in sorted(TOOL_HANDLERS):
        render.console.print(f"• {name}")
    render.console.print(f"\n[dim]{len(TOOL_HANDLERS)} tools[/dim]")


if __name__ == "__main__":
    app()
