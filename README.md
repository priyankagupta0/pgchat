# PgChat

**Natural language Postgres database operator powered by Google Gemini and MCP**

PgChat lets you interact with your PostgreSQL database using plain English. Ask questions, explore schemas, and run queries without writing SQL - all with enterprise-grade security that enforces read-only access.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **🗣️ Natural Language Interface**: Ask questions in plain English, get SQL results
- **🔒 Read-Only by Default**: Multi-layer security prevents destructive operations
- **🤖 Gemini-Powered**: Uses Google's latest Gemini models for intelligent query generation
- **🔌 MCP Protocol**: Exposes database as a Model Context Protocol server
- **📊 Beautiful Output**: Rich terminal UI with formatted tables and colors
- **🔄 Connection Pooling**: Production-ready asyncpg connection management
- **📝 Comprehensive Logging**: Centralized logging with file rotation
- **⚙️ Flexible Configuration**: Environment variables and config file support

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pgchat.git
cd pgchat

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Initial Setup

1. **Create configuration file**:
```bash
pgchat init
```

2. **Edit `~/.pgchat/config.toml`** with your credentials:
```toml
# Get API key from https://aistudio.google.com/apikey
gemini_api_key = "your-gemini-api-key-here"

# Your PostgreSQL connection string
database_url = "postgresql://user:password@localhost:5432/mydb"

# Model to use (default: gemini-2.5-flash)
gemini_model = "gemini-2.5-flash"
```

3. **Verify configuration**:
```bash
pgchat doctor
```

### Basic Usage

**Interactive Chat**:
```bash
pgchat chat
```

Example conversation:
```
pgchat> Show me all tables in the database
Tool call: run_query({"sql": "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"})

┏━━━━━━━━━━━━━━┓
┃ tablename    ┃
┡━━━━━━━━━━━━━━┩
│ users        │
│ products     │
│ orders       │
└──────────────┘
3 row(s) in 12.50 ms

pgchat> How many active users do we have?
Tool call: run_query({"sql": "SELECT COUNT(*) as active_users FROM users WHERE status = 'active'"})

┏━━━━━━━━━━━━━━┓
┃ active_users ┃
┡━━━━━━━━━━━━━━┩
│ 1,234        │
└──────────────┘
1 row(s) in 8.30 ms
```

**MCP Server Mode**:
```bash
pgchat mcp
```

Use with Claude Desktop or other MCP clients to expose your database as a tool.

## 📖 Documentation

### Commands

| Command | Description |
|---------|-------------|
| `pgchat init` | Create default configuration file |
| `pgchat chat` | Start interactive chat session |
| `pgchat mcp` | Start MCP server (stdio transport) |
| `pgchat doctor` | Validate configuration and environment |
| `pgchat version` | Display version information |

### Configuration

**Configuration File**: `~/.pgchat/config.toml`

```toml
# Required settings
gemini_api_key = "your-api-key"
database_url = "postgresql://user:pass@host:port/database"

# Optional settings (with defaults)
gemini_model = "gemini-2.5-flash"
query_limit = 100                    # Max rows returned per query
statement_timeout_ms = 10000         # Query timeout (10 seconds)
pool_min_size = 1                    # Min database connections
pool_max_size = 10                   # Max database connections
```

**Environment Variables**:

```bash
# Override config file
export PGCHAT_GEMINI_API_KEY="your-key"
export PGCHAT_DATABASE_URL="postgresql://..."

# Logging
export PGCHAT_LOG_LEVEL="DEBUG"           # Console: DEBUG, INFO, WARNING, ERROR
export PGCHAT_DISABLE_FILE_LOG="1"        # Disable file logging

# All config options
export PGCHAT_GEMINI_MODEL="gemini-2.5-flash"
export PGCHAT_QUERY_LIMIT="100"
export PGCHAT_STATEMENT_TIMEOUT_MS="10000"
export PGCHAT_POOL_MIN_SIZE="1"
export PGCHAT_POOL_MAX_SIZE="10"
```

### Security

PgChat implements **defense-in-depth** security:

1. **Application-level filtering**: Blocks non-SELECT queries before execution
2. **Database transaction isolation**: `SET TRANSACTION READ ONLY`
3. **Statement timeout**: Hard limit prevents runaway queries
4. **Connection pooling**: Resource limits and recycling
5. **No elevated privileges**: Works with standard read-only database users

**Blocked Operations**:
- `INSERT`, `UPDATE`, `DELETE`
- `DROP`, `TRUNCATE`, `ALTER`
- `CREATE`, `GRANT`, `REVOKE`
- Any DDL or DML operations

**Allowed Operations**:
- `SELECT` (with joins, CTEs, subqueries)
- `WITH` (Common Table Expressions)
- `SHOW` (configuration inspection)
- `EXPLAIN` (query analysis)
- `VALUES` (inline data)

## 🏗️ Architecture

```
pgchat/
├── agent/               # Gemini AI agent
│   ├── gemini_agent.py  # Function calling & tool execution
│   └── prompts.py       # System prompts
├── cli.py               # Command-line interface
├── config.py            # Pydantic settings management
├── db/
│   └── pool.py          # AsyncPG connection pooling
├── logging_config.py    # Centralized logging
├── mcp_server/
│   └── server.py        # MCP protocol server
├── tools/
│   └── query.py         # Query execution & safety
└── ui/
    └── render.py        # Rich terminal rendering
```

**Key Technologies**:
- **[Google Gemini](https://ai.google.dev/)**: AI model for natural language understanding
- **[MCP](https://modelcontextprotocol.io/)**: Model Context Protocol for tool integration
- **[asyncpg](https://github.com/MagicStack/asyncpg)**: High-performance PostgreSQL driver
- **[Pydantic](https://docs.pydantic.dev/)**: Data validation and settings
- **[Rich](https://github.com/Textualize/rich)**: Beautiful terminal output
- **[Typer](https://typer.tiangolo.com/)**: Modern CLI framework

## 🧪 Development

### Setup Development Environment

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pgchat --cov-report=html

# Run specific test file
pytest tests/test_query.py

# Run specific test
pytest tests/test_query.py::TestReadOnlyDetection::test_select_queries_allowed

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Project Structure

```
pgchat/
├── pgchat/              # Main package
├── tests/               # Test suite
│   ├── conftest.py      # Pytest fixtures
│   ├── test_query.py    # Query execution tests
│   ├── test_config.py   # Configuration tests
│   ├── test_logging.py  # Logging tests
│   └── test_render.py   # UI rendering tests
├── pyproject.toml       # Project metadata & dependencies
├── README.md            # This file
└── LOGGING.md           # Logging documentation
```

## 🐛 Troubleshooting

### Connection Issues

```bash
# Check configuration
pgchat doctor

# Test database connection
psql "postgresql://user:pass@host:port/db"

# Check logs
tail -f ~/.pgchat/logs/pgchat.log
```

### Debug Mode

```bash
# Enable debug logging
export PGCHAT_LOG_LEVEL=DEBUG
pgchat chat

# View detailed logs
cat ~/.pgchat/logs/pgchat.log
```

### Common Issues

**"Missing Gemini API key"**
- Get a key from https://aistudio.google.com/apikey
- Add to `~/.pgchat/config.toml` or set `PGCHAT_GEMINI_API_KEY`

**"Database connection failed"**
- Verify PostgreSQL is running
- Check connection string format
- Ensure user has SELECT permissions

**"No rows returned"**
- Query might be filtering out all results
- Check database has data: `pgchat> show me table counts`

## 📚 Examples

### Exploring Schema

```bash
pgchat> What tables exist?
pgchat> Describe the users table structure
pgchat> Show me the indexes on the orders table
```

### Data Analysis

```bash
pgchat> What's the average order value?
pgchat> Show top 5 customers by total purchases
pgchat> How many orders were placed last month?
```

### Query Performance

```bash
pgchat> Explain the query plan for selecting from large_table
pgchat> Show current database configuration
pgchat> What's the database version?
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Gemini team for the powerful AI models
- Anthropic for the MCP protocol specification
- The Python community for excellent libraries

## 📮 Contact

- **Author**: Priyanka Gupta
- **Issues**: [GitHub Issues](https://github.com/yourusername/pgchat/issues)

---

**Note**: PgChat is designed for read-only database operations. Never grant write permissions to the database user used by PgChat.
