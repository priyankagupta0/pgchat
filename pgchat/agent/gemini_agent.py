from __future__ import annotations

import json
import sys
from typing import Any

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from pgchat.agent.prompts import SYSTEM_PROMPT
from pgchat.config import Config
from pgchat.safety.approve import console_approve, needs_approval
from pgchat.safety.audit import log_event
from pgchat.safety.classify import classify_sql, classify_tool
from pgchat.ui import render


def _mcp_server_params(config: Config) -> StdioServerParameters:
    import os

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "pgchat.mcp_server.server"],
        env=env,
    )


def _schema_to_gemini_declaration(tool: Any) -> types.FunctionDeclaration:
    raw = dict(tool.inputSchema or {"type": "object", "properties": {}})
    # Gemini expects a simplified JSON Schema object.
    parameters = {
        "type": "object",
        "properties": raw.get("properties") or {},
    }
    if "required" in raw:
        parameters["required"] = raw["required"]
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or tool.name,
        parameters=parameters,
    )


def _extract_function_calls(response: types.GenerateContentResponse) -> list[types.FunctionCall]:
    calls: list[types.FunctionCall] = []
    if not response.candidates:
        return calls
    content = response.candidates[0].content
    if not content or not content.parts:
        return calls
    for part in content.parts:
        if part.function_call and part.function_call.name:
            calls.append(part.function_call)
    return calls


def _extract_text(response: types.GenerateContentResponse) -> str:
    try:
        return response.text or ""
    except Exception:  # noqa: BLE001
        texts: list[str] = []
        if not response.candidates:
            return ""
        content = response.candidates[0].content
        if not content or not content.parts:
            return ""
        for part in content.parts:
            if part.text:
                texts.append(part.text)
        return "\n".join(texts)


class GeminiAgent:
    def __init__(self, config: Config, console: Console | None = None):
        self.config = config
        self.console = console or render.console
        if not config.gemini.api_key:
            raise ValueError(
                "Gemini API key missing. Set gemini.api_key in ~/.pgchat/config.toml "
                "or export GEMINI_API_KEY."
            )
        self.client = genai.Client(api_key=config.gemini.api_key)
        self.history: list[types.Content] = []

    async def run_session(self) -> None:
        params = _mcp_server_params(self.config)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                gemini_tools = [
                    types.Tool(
                        function_declarations=[
                            _schema_to_gemini_declaration(t) for t in tools.tools
                        ]
                    )
                ]
                render.print_info(f"MCP ready — {len(tools.tools)} tools loaded.")
                render.print_banner()
                render.print_info("Type a question, or /exit to quit. /clear resets history.")

                while True:
                    try:
                        user_text = self.console.input("\n[bold cyan]›[/bold cyan] ").strip()
                    except (EOFError, KeyboardInterrupt):
                        self.console.print("\nBye.")
                        break
                    if not user_text:
                        continue
                    if user_text in {"/exit", "/quit", ":q"}:
                        self.console.print("Bye.")
                        break
                    if user_text == "/clear":
                        self.history.clear()
                        render.print_info("History cleared.")
                        continue

                    try:
                        answer = await self._turn(session, gemini_tools, user_text)
                        if answer:
                            render.print_assistant(answer)
                    except Exception as exc:  # noqa: BLE001
                        render.print_error(str(exc))
                        log_event(
                            action="agent_error",
                            error=str(exc),
                            enabled=self.config.safety.audit_enabled,
                        )

    async def ask_once(self, prompt: str) -> str:
        params = _mcp_server_params(self.config)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                gemini_tools = [
                    types.Tool(
                        function_declarations=[
                            _schema_to_gemini_declaration(t) for t in tools.tools
                        ]
                    )
                ]
                return await self._turn(session, gemini_tools, prompt)

    async def _turn(
        self,
        session: ClientSession,
        gemini_tools: list[types.Tool],
        user_text: str,
    ) -> str:
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=self.config.gemini.temperature,
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        final_text = ""
        for _ in range(self.config.gemini.max_tool_rounds):
            response = await self.client.aio.models.generate_content(
                model=self.config.gemini.model,
                contents=self.history,
                config=config,
            )
            model_content = (
                response.candidates[0].content
                if response.candidates and response.candidates[0].content
                else None
            )
            if model_content is None:
                break

            self.history.append(model_content)
            text = _extract_text(response)
            if text:
                render.print_reasoning(text)
                final_text = text

            calls = _extract_function_calls(response)
            if not calls:
                break

            fn_response_parts: list[types.Part] = []
            for call in calls:
                name = call.name or "unknown"
                args = dict(call.args or {})
                result = await self._execute_tool(session, name, args)
                fn_response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response={"result": result},
                    )
                )
            self.history.append(types.Content(role="user", parts=fn_response_parts))
        else:
            final_text = final_text or "Stopped after max tool rounds."

        return final_text

    async def _execute_tool(self, session: ClientSession, name: str, args: dict[str, Any]) -> str:
        classification = classify_tool(name)
        if name in {"run_query", "explain_query", "apply_migration"} and "sql" in args:
            classification = classify_sql(
                str(args["sql"]),
                block_drop_database=self.config.safety.block_drop_database,
            )

        render.print_tool_call(name, args)

        if classification.blocked:
            msg = f"Blocked by policy: {classification.reason}"
            render.print_error(msg)
            log_event(
                action="blocked",
                tool=name,
                risk=classification.risk,
                args=args,
                error=msg,
                enabled=self.config.safety.audit_enabled,
            )
            return json.dumps({"error": msg})

        approved = True
        if needs_approval(classification, self.config.safety):
            approved = console_approve(name, classification, args, self.console)
            if not approved:
                log_event(
                    action="denied",
                    tool=name,
                    risk=classification.risk,
                    args=args,
                    approved=False,
                    enabled=self.config.safety.audit_enabled,
                )
                return json.dumps({"error": "User denied this action."})

        try:
            result = await session.call_tool(name, arguments=args)
            text_parts = []
            for block in result.content:
                text = getattr(block, "text", None)
                if text:
                    text_parts.append(text)
            output = "\n".join(text_parts) if text_parts else json.dumps({"ok": True})
            if getattr(result, "isError", False):
                render.print_error(output)
            else:
                render.print_tool_result(name, output)
            log_event(
                action="tool_call",
                tool=name,
                risk=classification.risk,
                args=args,
                result_summary=output,
                approved=approved,
                enabled=self.config.safety.audit_enabled,
            )
            return output
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            render.print_error(err)
            log_event(
                action="tool_error",
                tool=name,
                risk=classification.risk,
                args=args,
                error=err,
                approved=approved,
                enabled=self.config.safety.audit_enabled,
            )
            return json.dumps({"error": err})
