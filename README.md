# pgchat

**Talk to your Postgres in plain English.**  
It doesn't just generate SQL — it **monitors, optimizes, migrates, and heals** your database through a local [MCP](https://modelcontextprotocol.io/) tool server, Gemini function calling, and a human-in-the-loop safety layer.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-see%20LICENSE-lightgrey.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-21%20tools-green.svg)](#mcp-tool-catalog)

```bash
uv sync && uv run pgchat init && uv run pgchat chat
```

---

## Why pgchat?

Most “text-to-SQL” demos stop at `SELECT`. Real DBA work is operational:

| Typical chatbot | pgchat |
| --- | --- |
| Writes a query and hopes you run it | Executes via MCP tools against your DB |
| Read-only exploration | Query **and** operate (indexes, vacuum, kill runaway backends, migrations) |
| Cloud round-trip of your schema/data | Runs **on your machine** — DB stays in your network |
| Blind trust in the model | SQL risk classification + approvals + audit log |

**One line:** an open-source, pip-installable CLI that embeds a local MCP server so an LLM can act like a junior DBA — with brakes.

---

## Features

- **Natural language CLI** — chat with Postgres using your own Gemini API key
- **Local MCP server** — 21 curated database-ops tools over stdio (usable from pgchat *or* Cursor / Claude Desktop)
- **Visible agent loop** — reasoning text, tool calls, and Rich tables in the terminal
- **Safety layer** — deterministic SQL classification, HITL approval for write/DDL/admin, hard block on `DROP DATABASE`
- **Production-minded defaults** — asyncpg pool, statement timeout, row caps, schema cache, JSONL audit trail
- **Ops beyond SELECT** — slow queries, locks, connections, index suggestions, vacuum, migrations with rollback

---

## Architecture

```text
┌─────────────────┐     natural language      ┌──────────────────────┐
│  You (CLI)      │ ────────────────────────► │  Gemini (your key)   │
└────────┬────────┘                           └──────────┬───────────┘
         │                                               │
         │ Rich UI (reasoning / approvals / tables)      │ function calls
         ▼                                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                     pgchat agent loop                               │
│  classify risk → approve if needed → call MCP tool → audit log     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ MCP (stdio)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                     pgchat MCP server                               │
│  run_query · explain · schema · indexes · health · kill · migrate  │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ asyncpg pool
                              ▼
                     ┌─────────────────┐
                     │  PostgreSQL     │
                     └─────────────────┘
```

### Request lifecycle

1. You type a request in `pgchat chat` (or a host app calls the MCP server).
2. Gemini receives the system prompt + conversation + **MCP tool schemas**.
3. The model may reply with text and/or one or more tool calls.
4. Before each tool runs, pgchat:
   - classifies risk (`read` / `write` / `ddl` / `destructive` / `admin`)
   - blocks policy violations (e.g. `DROP DATABASE`)
   - prompts for approval when configured
   - writes an audit event
5. The MCP server executes against Postgres through a shared **asyncpg** pool.
6. Results are returned to Gemini for the next reasoning step (multi-round tool use).

Everything except the Gemini API call stays local. Query results and schema details are not sent to a third-party DB agent SaaS — only to the model provider you configure (Gemini).

---

## Quick start

### Requirements

- Python **3.11+**
- A reachable **PostgreSQL** instance
- A **Gemini API key** ([Google AI Studio](https://aistudio.google.com/apikey))
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip

### Install & run

```bash
git clone https://github.com/<you>/pgchat.git
cd pgchat
uv sync

uv run pgchat init          # interactive: DB + API key → ~/.pgchat/config.toml
uv run pgchat chat          # interactive REPL
uv run pgchat chat "what's the health of my database?"
```

Or with pip:

```bash
pip install -e .
pgchat init
pgchat chat
```

### Environment overrides

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini key if not set in config |
| `PGCHAT_CONFIG` | Path to an alternate `config.toml` (used by the MCP server) |

---

## CLI reference

| Command | Description |
| --- | --- |
| `pgchat init` | Create `~/.pgchat/config.toml` |
| `pgchat init --non-interactive` | Write defaults without prompts |
| `pgchat chat` | Interactive agent REPL (`/exit`, `/clear`) |
| `pgchat chat "…"` | One-shot question |
| `pgchat mcp` | Run the MCP server on **stdio** |
| `pgchat tools` | List built-in tool names |

---

## Configuration

Default path: **`~/.pgchat/config.toml`**

```toml
[database]
host = "localhost"
port = 5432
user = "postgres"
password = "secret"
database = "app"
min_pool_size = 1
max_pool_size = 5
statement_timeout_ms = 30000

[gemini]
api_key = ""   # or set GEMINI_API_KEY
model = "gemini-2.0-flash"
temperature = 0.1
max_tool_rounds = 12

[safety]
require_approval_for = ["write", "ddl", "destructive", "admin"]
auto_approve_read = true
block_drop_database = true
max_rows = 500
audit_enabled = true

default_schema = "public"
```

### Local data layout

```text
~/.pgchat/
├── config.toml           # connection + model + safety
├── audit/
│   └── audit-YYYY-MM-DD.jsonl
└── schema_cache/
    └── <database>.json   # TTL-cached table/column metadata
```

---

## MCP tool catalog

21 tools, grouped by job:

### Query

| Tool | What it does |
| --- | --- |
| `run_query` | Execute SQL; SELECTs return capped JSON rows |
| `explain_query` | `EXPLAIN` / `EXPLAIN ANALYZE` as JSON |

### Schema

| Tool | What it does |
| --- | --- |
| `list_tables` | Tables/views in a schema |
| `describe_table` | Columns, PKs, FKs |
| `list_indexes` | Indexes on a table |
| `get_table_stats` | Size + estimated rows |
| `get_schema_cache` | Read (or refresh) local schema cache |
| `refresh_schema_cache` | Rebuild cache |

### Performance

| Tool | What it does |
| --- | --- |
| `get_slow_queries` | Top queries via `pg_stat_statements` (if installed) |
| `suggest_indexes` | Heuristics: seq scans, missing FK indexes, unused indexes |
| `create_index` | Create index (`CONCURRENTLY` by default) |
| `drop_index` | Drop index |
| `vacuum_analyze` | `VACUUM ANALYZE` table or database |

### Administration

| Tool | What it does |
| --- | --- |
| `check_health` | Version, size, connections, cache hit ratio |
| `get_connections` | `pg_stat_activity` snapshot |
| `get_locks` | Lock / wait activity |
| `kill_query` | `pg_cancel_backend` / `pg_terminate_backend` |
| `get_replication_status` | Slots + replication lag |

### Migrations

| Tool | What it does |
| --- | --- |
| `apply_migration` | Run SQL + record in `pgchat_migrations` |
| `rollback_migration` | Apply stored `rollback_sql` |
| `list_migrations` | History of applied / rolled-back migrations |

---

## Safety model

pgchat assumes the model can be wrong. Guardrails are **deterministic**, not prompt-only.

### Risk levels

| Level | Examples | Default |
| --- | --- | --- |
| `read` | `SELECT`, `EXPLAIN`, schema inspection | Auto-approved |
| `write` | `INSERT` / `UPDATE` / `DELETE` **with** `WHERE` | Approval required |
| `ddl` | `CREATE` / `ALTER` / `VACUUM` | Approval required |
| `destructive` | `DROP` / `TRUNCATE` / DELETE·UPDATE **without** `WHERE` | Approval required |
| `admin` | `kill_query`, cancel/terminate backends | Approval required |

### Hard policy

- **`DROP DATABASE` is always blocked** (when `block_drop_database = true`).
- SELECT results are capped by `safety.max_rows` (default 500).
- Pool uses Postgres `statement_timeout` from config.
- Denied / blocked / executed actions are appended to the daily audit JSONL.

Approvals appear in the CLI as a Rich panel before the MCP tool runs — the model cannot silently skip them when `require_approval_for` includes that risk class.

---

## Use as an MCP server (Cursor / Claude Desktop)

pgchat chat embeds the MCP server as a subprocess. You can also register it as a standalone MCP server for other clients:

```json
{
  "mcpServers": {
    "pgchat": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/pgchat", "pgchat", "mcp"]
    }
  }
}
```

Or after install:

```json
{
  "mcpServers": {
    "pgchat": {
      "command": "pgchat",
      "args": ["mcp"]
    }
  }
}
```

Ensure `~/.pgchat/config.toml` (or `PGCHAT_CONFIG`) points at the database you intend the host app to operate on. **Host-embedded MCP bypasses the CLI approval UI** — tighten DB credentials / use a read-only role when exposing tools to an IDE agent.

---

## Project structure

```text
pgchat/
├── cli.py                 # Typer entry: init / chat / mcp / tools
├── config.py              # Pydantic settings + ~/.pgchat paths
├── __main__.py
├── agent/
│   ├── gemini_agent.py    # Gemini ↔ MCP session loop + approvals
│   └── prompts.py         # System prompt (DBA operator persona)
├── mcp_server/
│   ├── server.py          # FastMCP app + lifespan (pool init)
│   └── __main__.py
├── tools/
│   ├── query.py           # run / explain
│   ├── schema.py          # introspect + schema cache
│   ├── performance.py     # slow queries / indexes / vacuum
│   ├── admin.py           # health / locks / kill / replication
│   └── migration.py       # apply / rollback / list
├── safety/
│   ├── classify.py        # SQL + tool risk classification
│   ├── approve.py         # HITL gate
│   └── audit.py           # JSONL audit writer
├── db/
│   └── pool.py            # asyncpg pool lifecycle
└── ui/
    └── render.py          # Rich banners, tables, tool panels
```

---

## Technical deep dive

### Stack

| Layer | Choice | Why |
| --- | --- | --- |
| CLI | Typer + Rich | Fast UX, markdown/tables, approval prompts |
| LLM | `google-genai` (Gemini) | Native function calling; user-owned API key |
| Tool protocol | MCP (FastMCP, stdio) | Standard tool surface for CLI *and* IDE hosts |
| DB driver | asyncpg pool | Low-latency async Postgres; statement timeout |
| Config | Pydantic + TOML | Typed, validated, human-editable |

### Agent ↔ MCP integration

The chat command does **not** call tool Python functions directly. It:

1. Spawns `python -m pgchat.mcp_server.server` over stdio  
2. Opens an MCP `ClientSession` and `list_tools()`  
3. Converts MCP JSON Schemas into Gemini `FunctionDeclaration`s  
4. Runs `generate_content` with **automatic function calling disabled**  
5. Intercepts each `function_call`, applies safety, then `session.call_tool(...)`  
6. Feeds `function_response` parts back into the conversation until the model returns plain text  

That keeps a single source of truth for tools (the MCP server) while letting the CLI own policy and UX.

### SQL classification

Classification is regex/heuristic over the statement text (not the planner):

- Prefer **read** for `SELECT` / `WITH … SELECT` / `EXPLAIN` / `SHOW`
- Escalate DELETE/UPDATE **without** `WHERE` to **destructive**
- Map DDL keywords and admin functions to `ddl` / `admin`
- Unknown statements default to **write** (fail closed on auto-approve)

Tool names also have a static risk map (e.g. `kill_query` → `admin`) so non-SQL tools are gated too.

### Schema cache

`get_schema_cache` / `refresh_schema_cache` persist table/column metadata under `~/.pgchat/schema_cache/` with a short TTL. The agent is prompted to ground itself on real schema before inventing SQL — reducing hallucinated table names.

### Migrations

`apply_migration` runs user SQL inside a transaction and inserts a row into `pgchat_migrations` (created on demand), optionally storing `rollback_sql`. `rollback_migration` reapplies that reverse script and stamps `rolled_back_at`.

---

## Example session

```text
› how healthy is my database and are there any idle-in-transaction sessions?

Reasoning
─────────
I'll check overall health, then inspect active connections…

Tool → check_health
Tool → get_connections

pgchat
──────
Your DB is healthy: Postgres 16.x, cache hit ~99%, 12/100 connections…
Two idle-in-transaction backends (pids 4412, 4418) have been open > 10 minutes.
I can cancel them if you want — say the word.
```

Write/DDL paths show an **Approval required** panel before execution.

---

## Development

```bash
uv sync
uv run pgchat tools
uv run python -c "from tests.test_classify import *; \
  test_select_is_read(); test_drop_database_blocked(); print('ok')"
```

### Design principles

1. **Operate, don’t only narrate** — tools must execute, not just suggest  
2. **One tool surface** — MCP is the API; CLI and IDE hosts share it  
3. **Safety outside the prompt** — classification + approval + audit  
4. **Local by default** — pool and MCP run on the operator’s machine  

---

## Security notes

- Prefer a **least-privilege DB role** for day-to-day chat; escalate only when needed  
- Treat `~/.pgchat/config.toml` like a secrets file (password + API key)  
- Audit logs may contain SQL text — protect `~/.pgchat/audit/` accordingly  
- When wiring `pgchat mcp` into an IDE, remember the IDE agent may not use CLI approvals  

---

## Roadmap (ideas)

- [ ] Read-only connection mode / dual-role (inspect vs change)  
- [ ] Streaming token UI for long model replies  
- [ ] Optional OpenAI / Anthropic backends behind the same MCP tools  
- [ ] Deeper `pg_stat_statements` + auto-EXPLAIN workflows  
- [ ] Packaged MCP install metadata for one-click Cursor setup  

---

## Contributing

Issues and PRs are welcome. Please keep changes focused:

1. Prefer extending `pgchat/tools/*` + registering on the FastMCP server  
2. Add/adjust risk mapping in `pgchat/safety/classify.py` for new tools  
3. Avoid logging secrets; scrub passwords in audit payloads (already sanitized by key name)

---

## License

See [`LICENSE`](LICENSE) in this repository.

---

## Acknowledgments

Built on [MCP](https://modelcontextprotocol.io/), [asyncpg](https://magicstack.github.io/asyncpg/), [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), and the [Google Gen AI SDK](https://googleapis.github.io/python-genai/).
