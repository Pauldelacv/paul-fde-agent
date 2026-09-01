# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""Structured run logging.

One JSON object per run, one run per line (JSONL), appended to
``$PFA_LOG_DIR/runs-YYYY-MM-DD.jsonl``. JSONL is chosen over a database because
it survives crashes, is greppable with `jq`, rotates by date for free, and can
be shipped to any log pipeline without an exporter.

Every value written here passes through :func:`redact` first. A log file is the
most common way secrets leak out of an otherwise careful system.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = Path("var/logs")

# Patterns that look like credentials regardless of the key they sit under.
_SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),  # OpenAI / Anthropic style
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),  # GitHub tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),  # Slack tokens
    re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_\-]{30,}"),  # Telegram bot tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}"),
]

# Keys whose value is replaced wholesale, whatever it looks like.
_SECRET_KEY_HINTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "credential",
    "private_key",
)

REDACTED = "***redacted***"


def redact(value: Any) -> Any:
    """Strip credential-shaped data from anything about to be written to disk."""
    if isinstance(value, str):
        out = value
        for pattern in _SECRET_VALUE_PATTERNS:
            out = pattern.sub(REDACTED, out)
        return out
    if isinstance(value, dict):
        return {
            k: (REDACTED if any(h in str(k).lower() for h in _SECRET_KEY_HINTS) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


@dataclass
class RunRecord:
    """One agent run, from routing decision to exit status."""

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    task: str = ""
    task_basis: str = ""
    provider: str = ""
    model: str = ""
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    duration_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    status: str = "unknown"  # success | error | denied
    exit_code: int | None = None
    error: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return redact(asdict(self))


def log_dir() -> Path:
    return Path(os.environ.get("PFA_LOG_DIR") or DEFAULT_LOG_DIR)


def write_record(record: RunRecord, directory: Path | None = None) -> Path:
    """Append a run record as one JSON line. Returns the file written to.

    Logging must never take down a run: if the directory cannot be created or
    written, the caller gets the exception and decides — but the agent's own
    result is already in hand by the time this is called.
    """
    target_dir = directory or log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    date = record.timestamp[:10]
    path = target_dir / f"runs-{date}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path
