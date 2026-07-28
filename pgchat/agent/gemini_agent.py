"""Gemini-powered AI agent for natural language database interactions."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from pgchat.agent.prompts import SYSTEM_PROMPT
from pgchat.config import Settings
from pgchat.logging_config import get_logger
from pgchat.tools.query import QueryResult, run_query
from pgchat.ui.render import QueryRenderer

logger = get_logger(__name__)


# Gemini function declaration for SQL query execution
RUN_QUERY_DECLARATION = types.FunctionDeclaration(
    name="run_query",
    description=(
        "Execute a read-only SQL query against Postgres. "
        "Only SELECT, WITH, SHOW, and EXPLAIN are allowed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "Read-only SQL query to execute.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of rows to return. Default 100.",
            },
        },
        "required": ["sql"],
    },
)


class GeminiAgent:
    """
    Production-ready Gemini-powered agent for natural language Postgres queries.

    Handles:
    - Function calling and tool execution
    - Query result rendering
    - Error handling and logging
    - Interactive chat loop
    """

    def __init__(
        self,
        settings: Settings,
        console: Console | None = None,
        renderer: QueryRenderer | None = None,
    ) -> None:
        """
        Initialize the Gemini agent.

        Args:
            settings: Application settings containing API keys and config.
            console: Optional Rich Console for output. Creates new one if not provided.
            renderer: Optional QueryRenderer for result formatting.

        Raises:
            ValueError: If Gemini API key is not configured.
        """
        if not settings.gemini_api_key:
            raise ValueError(
                "Missing Gemini API key. Set PGCHAT_GEMINI_API_KEY or run pgchat init."
            )

        self.settings = settings
        self.console = console or Console()
        self.renderer = renderer or QueryRenderer(self.console)

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.tool = types.Tool(function_declarations=[RUN_QUERY_DECLARATION])
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[self.tool],
            temperature=0.1,
        )
        self.history: list[types.Content] = []

        logger.info(f"Initialized GeminiAgent with model: {settings.gemini_model}")

    async def execute_tool(self, name: str, args: dict[str, Any]) -> QueryResult:
        """
        Execute a tool by name with given arguments.

        Args:
            name: Tool name (currently only 'run_query' is supported).
            args: Tool arguments dictionary.

        Returns:
            QueryResult containing execution results or error information.
        """
        if name != "run_query":
            logger.warning(f"Unknown tool requested: {name}")
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                duration_ms=0.0,
                truncated=False,
                error={
                    "code": "UNKNOWN_TOOL",
                    "message": f"Unknown tool: {name}",
                    "hint": "Available tools: run_query",
                },
            )

        try:
            sql = args.get("sql")
            if not sql:
                return QueryResult(
                    columns=[],
                    rows=[],
                    row_count=0,
                    duration_ms=0.0,
                    truncated=False,
                    error={
                        "code": "MISSING_SQL",
                        "message": "SQL query is required",
                        "hint": "Provide a SQL query string",
                    },
                )

            limit = int(args.get("limit", self.settings.query_limit))
            logger.info(f"Executing query with limit {limit}: {sql[:100]}...")

            return await run_query(sql=sql, limit=limit)

        except ValueError as e:
            logger.error(f"Invalid tool arguments: {e}")
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                duration_ms=0.0,
                truncated=False,
                error={
                    "code": "INVALID_ARGUMENTS",
                    "message": str(e),
                    "hint": "Check tool argument types and values",
                },
            )
        except Exception as e:
            logger.exception("Unexpected error executing tool")
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                duration_ms=0.0,
                truncated=False,
                error={
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": "Tool execution failed unexpectedly",
                },
            )

    def extract_function_call(self, response: Any) -> types.FunctionCall | None:
        """
        Extract function call from Gemini response if present.

        Args:
            response: Gemini API response object.

        Returns:
            FunctionCall object if found, None otherwise.
        """
        try:
            parts = response.candidates[0].content.parts
            for part in parts:
                if function_call := getattr(part, "function_call", None):
                    return function_call
        except (AttributeError, IndexError, TypeError) as e:
            logger.debug(f"No function call found in response: {e}")

        return None

    def _serialize_result(self, result: QueryResult) -> dict[str, Any]:
        """Convert a QueryResult to a JSON-serialisable dict for Gemini."""
        if result.error:
            return {"error": result.error}
        return {
            "columns": result.columns,
            "rows": [
                {k: str(v) if v is not None else None for k, v in row.items()}
                for row in result.rows
            ],
            "row_count": result.row_count,
            "duration_ms": result.duration_ms,
            "truncated": result.truncated,
        }

    async def run_turn(self, user_input: str) -> None:
        """
        Run one complete conversational turn.

        Appends the user message to history, then loops through Gemini
        responses — executing any tool calls and feeding results back —
        until a final text response is produced.
        """
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=self.history,
                    config=self.config,
                )
            except Exception:
                logger.exception("Gemini API call failed")
                raise

            model_content = response.candidates[0].content
            self.history.append(model_content)

            if function_call := self.extract_function_call(response):
                tool_name = function_call.name
                tool_args = dict(function_call.args or {})
                sql = tool_args.get("sql", "")

                self.console.print()
                if sql:
                    self.console.print(
                        Panel(
                            Syntax(sql.strip(), "sql", theme="monokai", word_wrap=True),
                            title="[dim]querying[/dim]",
                            border_style="dim",
                            padding=(0, 1),
                        )
                    )
                else:
                    self.console.print(f"[dim]calling {tool_name}…[/dim]")

                result = await self.execute_tool(tool_name, tool_args)
                self.console.print()
                self.renderer.render(result)

                # Feed the tool result back so Gemini can narrate / reason further
                self.history.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=tool_name,
                                    response=self._serialize_result(result),
                                )
                            )
                        ],
                    )
                )
                continue

            if text := getattr(response, "text", None):
                self.console.print()
                self.console.print(
                    Panel(
                        Markdown(text),
                        title="[bold cyan]pgchat[/bold cyan]",
                        border_style="cyan",
                        padding=(0, 1),
                    )
                )
                return

            self.console.print("[yellow]No response received.[/yellow]")
            return

    async def run_interactive(self) -> None:
        """
        Run the interactive chat loop.

        Handles user input, Gemini responses, and graceful shutdown.
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold cyan]pgchat[/bold cyan]  ·  natural language postgres\n"
                f"[dim]model: {self.settings.gemini_model}   type [bold]exit[/bold] to quit[/dim]",
                border_style="cyan",
                padding=(0, 2),
            )
        )
        self.console.print()

        while True:
            try:
                self.console.rule(style="dim")
                user_input = self.console.input("\n[bold]pgchat[/bold]  ").strip()

                if user_input.lower() in {"exit", "quit", ":q", "q"}:
                    self.console.print()
                    self.console.print("[dim]goodbye[/dim]")
                    break

                if not user_input:
                    continue

                self.console.print()
                await self.run_turn(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[dim]interrupted — type exit to quit[/dim]")
                continue
            except EOFError:
                self.console.print("\n[dim]goodbye[/dim]")
                break
            except Exception as e:
                logger.exception("Error in chat loop")
                self.console.print(f"\n[red]error:[/red] {e}\n[dim]try again[/dim]")


async def run_chat(settings: Settings) -> None:
    """
    Convenience function to start an interactive chat session.

    Args:
        settings: Application settings.

    Raises:
        ValueError: If settings are invalid.
    """
    agent = GeminiAgent(settings)
    await agent.run_interactive()