from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pgchat.config import AUDIT_DIR


def _audit_path() -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit-{day}.jsonl"


def log_event(
    *,
    action: str,
    tool: str | None = None,
    risk: str | None = None,
    args: dict[str, Any] | None = None,
    result_summary: str | None = None,
    approved: bool | None = None,
    error: str | None = None,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "tool": tool,
        "risk": risk,
        "args": _sanitize(args or {}),
        "result_summary": (result_summary or "")[:2000],
        "approved": approved,
        "error": error,
    }
    path = _audit_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _sanitize(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in args.items():
        key = k.lower()
        if "password" in key or "secret" in key or "token" in key:
            out[k] = "***"
        elif isinstance(v, str) and len(v) > 2000:
            out[k] = v[:2000] + "…"
        else:
            out[k] = v
    return out
