# Contributing to PgChat

Thank you for your interest in contributing to PgChat! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and clone the repository**:
```bash
git clone https://github.com/yourusername/pgchat.git
cd pgchat
```

2. **Install dependencies**:
```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

3. **Set up configuration**:
```bash
pgchat init
# Edit ~/.pgchat/config.toml with your test database credentials
```

## Code Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use type hints for all function signatures
- Use `from __future__ import annotations` for forward references
- Keep functions focused and under 50 lines when possible
- Use descriptive variable names

### Formatting and Linting

```bash
# Format code with Ruff
ruff format .

# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Modern Python Practices

PgChat follows modern Python 3.11+ standards:

- ✅ Use `|` for union types instead of `Union` or `Optional`
- ✅ Use walrus operator `:=` where appropriate
- ✅ Use Pydantic models for data validation
- ✅ Use async/await for I/O operations
- ✅ Use f-strings for string formatting
- ✅ Use `match`/`case` for complex conditionals (when appropriate)

**Good Examples**:
```python
def process_data(value: str | None = None) -> dict[str, Any]:
    """Process data with modern type hints."""
    if result := expensive_operation(value):
        return {"success": True, "data": result}
    return {"success": False}
```

## Testing

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use descriptive test names: `test_feature_does_expected_thing`
- Group related tests in classes
- Use pytest fixtures from `conftest.py`

**Example Test**:
```python
def test_query_validation():
    """Test that invalid queries are rejected."""
    from pgchat.tools.query import is_readonly_sql
    
    assert is_readonly_sql("SELECT * FROM users")
    assert not is_readonly_sql("DELETE FROM users")
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_query.py

# Specific test
pytest tests/test_query.py::TestReadOnlyDetection::test_select_queries_allowed

# With coverage
pytest --cov=pgchat --cov-report=html

# Verbose
pytest -v

# Stop on first failure
pytest -x
```

### Test Coverage

- Aim for >80% code coverage
- Focus on critical paths (query execution, security, config)
- Don't test external dependencies (asyncpg, Gemini API)
- Use `@pytest.mark.skip` for tests requiring live databases

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief one-line description.

    More detailed description if needed. Can span multiple lines
    and include examples.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param2 is negative.

    Examples:
        >>> example_function("test", 42)
        True
    """
    pass
```

### Module Docstrings

Every Python file should start with a module docstring:

```python
"""Brief description of module purpose.

More detailed information about what this module does and how
it fits into the larger system.
"""
```

## Git Workflow

### Branching Strategy

- `main` - Stable, production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `refactor/*` - Code improvements without behavior changes

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Maintenance tasks

**Examples**:
```
feat(agent): add support for query history
fix(pool): handle connection timeouts gracefully
docs(readme): update installation instructions
test(query): add tests for CTE validation
```

### Pull Request Process

1. **Create a feature branch**:
```bash
git checkout -b feature/my-new-feature
```

2. **Make your changes**:
   - Write code
   - Add/update tests
   - Update documentation
   - Run tests and linting

3. **Commit with clear messages**:
```bash
git add .
git commit -m "feat(scope): add new feature"
```

4. **Push to your fork**:
```bash
git push origin feature/my-new-feature
```

5. **Open a Pull Request**:
   - Provide clear description of changes
   - Reference any related issues
   - Ensure CI checks pass
   - Wait for review

### PR Checklist

- [ ] Tests pass (`pytest`)
- [ ] Code is formatted (`ruff format .`)
- [ ] No linting errors (`ruff check .`)
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG updated (for significant changes)
- [ ] Type hints added/updated
- [ ] Commit messages follow conventions

## Architecture Decisions

### When to Add Dependencies

- Prefer standard library when possible
- Only add well-maintained, popular packages
- Justify new dependencies in PR description
- Update `pyproject.toml` appropriately

### Error Handling

- Use specific exception types
- Log exceptions with `logger.exception()`
- Provide helpful error messages
- Include recovery suggestions when possible

### Async Code

- Use `async`/`await` for I/O operations
- Avoid blocking calls in async functions
- Use `asyncio.create_task()` for concurrent operations
- Close resources properly with `async with`

### Logging

- Use centralized logger: `logger = get_logger(__name__)`
- Log at appropriate levels:
  - `DEBUG`: Implementation details
  - `INFO`: Important events
  - `WARNING`: Potential issues
  - `ERROR`: Failures
- Never log sensitive data (passwords, API keys)

## Reporting Issues

### Bug Reports

Include:
- PgChat version (`pgchat version`)
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and stack traces
- Relevant logs from `~/.pgchat/logs/`

### Feature Requests

Include:
- Use case / problem to solve
- Proposed solution
- Alternative solutions considered
- Additional context

## Code Review

### As an Author

- Keep PRs focused and small
- Respond to feedback promptly
- Don't take criticism personally
- Update PR based on feedback

### As a Reviewer

- Be respectful and constructive
- Focus on code, not the person
- Explain reasoning behind suggestions
- Approve when satisfied

## Questions?

- Open a [GitHub Discussion](https://github.com/yourusername/pgchat/discussions)
- Check existing issues and PRs
- Read the documentation

Thank you for contributing! 🎉
