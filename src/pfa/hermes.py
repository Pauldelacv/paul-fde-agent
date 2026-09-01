"""Integration with the Hermes Agent runtime.

Scope discipline: Hermes already owns the agent loop, the tool layer, the MCP
client, skills, memory, cron and the approval system. This module does not
reimplement any of that. It does exactly three things:

  1. locate the ``hermes`` executable and report its version,
  2. render ``$HERMES_HOME/config.yaml`` from our routing policy,
  3. build the ``hermes chat`` argv for a routed run.

Every flag used here was verified against the Hermes CLI reference on
2026-09-01 (repo v0.21.0). See docs/verified-facts.md.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import Config
from .router import Decision

DEFAULT_HERMES_HOME = Path("var/hermes")


# ---------------------------------------------------------------------------
# Autonomy levels
#
# The project spec calls for four levels. Hermes exposes an `approvals` block
# (mode: smart|manual|off, plus per-context modes and fnmatch deny globs) and a
# `terminal` backend. Our levels are a named mapping onto those real controls —
# not a new enforcement engine. Enforcement stays in Hermes, where the agent
# loop can actually block a call.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AutonomyLevel:
    number: int
    name: str
    summary: str
    approvals_mode: str  # Hermes `approvals.mode`
    unattended_mode: str  # Hermes `approvals.unattended_mode`
    cron_mode: str  # Hermes `approvals.cron_mode`


AUTONOMY_LEVELS: dict[str, AutonomyLevel] = {
    "read": AutonomyLevel(
        1,
        "read",
        "Read and analyse only. Every state-changing command requires approval.",
        approvals_mode="manual",
        unattended_mode="deny",
        cron_mode="deny",
    ),
    "propose": AutonomyLevel(
        2,
        "propose",
        "May draft changes and commands but must have each one confirmed.",
        approvals_mode="manual",
        unattended_mode="deny",
        cron_mode="deny",
    ),
    "execute": AutonomyLevel(
        3,
        "execute",
        "May run reversible actions unattended; risky patterns still prompt.",
        approvals_mode="smart",
        unattended_mode="deny",
        cron_mode="approve",
    ),
    "external": AutonomyLevel(
        4,
        "external",
        "May act on external or destructive targets. Explicit confirmation "
        "remains mandatory for the irreversible operations listed in DENY_GLOBS.",
        approvals_mode="smart",
        unattended_mode="deny",
        cron_mode="approve",
    ),
}

DEFAULT_AUTONOMY = "propose"

# Commands refused unconditionally, before any approval mode is consulted.
# fnmatch globs, matching the format Hermes documents for `approvals.deny`.
DENY_GLOBS: tuple[str, ...] = (
    "*rm -rf /*",
    "*mkfs*",
    "*dd if=*of=/dev/*",
    "*chmod 777*",
    "*DROP DATABASE*",
    "*DROP TABLE*",
    "*TRUNCATE TABLE*",
    "git push --force*",
    "git push -f*",
    "*curl*|*sh*",
    "*wget*|*sh*",
    "*> /etc/*",
    "*docker system prune*",
    "*terraform destroy*",
    "*kubectl delete namespace*",
)


class HermesNotInstalled(RuntimeError):
    """Raised when the Hermes runtime is needed but absent."""


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or DEFAULT_HERMES_HOME)


def find_hermes() -> str | None:
    """Absolute path to the ``hermes`` executable, or None if not on PATH."""
    return shutil.which("hermes")


def hermes_version(timeout: int = 15) -> str | None:
    """Installed Hermes version string, or None if unavailable.

    Never raises: this is used by ``pfa doctor``, whose whole job is to report
    a broken environment rather than fail inside it.
    """
    executable = find_hermes()
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0] if output else None


def render_config(
    config: Config, autonomy: str = DEFAULT_AUTONOMY, terminal: str = "local"
) -> dict:
    """Build the Hermes ``config.yaml`` document from our routing policy.

    API keys are emitted as ``${VAR}`` references, never as values. Hermes
    resolves them from ``$HERMES_HOME/.env`` at load time, so the rendered file
    stays safe to read, diff and back up.
    """
    level = AUTONOMY_LEVELS[autonomy]
    default_route = config.routes[config.default_task]
    default_provider = config.provider_for(default_route.provider)
    default_model = default_route.model or default_provider.default_model

    return {
        "_generated_by": (
            "paul-fde-agent — regenerate with `pfa hermes-config --write`. "
            "Local edits are overwritten."
        ),
        "model": f"{default_provider.name}/{default_model}",
        "providers": {
            name: {
                "base_url": provider.base_url,
                "api_key": f"${{{provider.api_key_env}}}",
            }
            for name, provider in config.providers.items()
        },
        "terminal": terminal,
        "approvals": {
            "mode": level.approvals_mode,
            "unattended_mode": level.unattended_mode,
            "cron_mode": level.cron_mode,
            "mcp_reload_confirm": True,
            "destructive_slash_confirm": True,
            "deny": list(DENY_GLOBS),
        },
        "skills": {"enabled": True},
    }


def write_config(
    config: Config,
    autonomy: str = DEFAULT_AUTONOMY,
    terminal: str = "local",
    home: Path | None = None,
) -> Path:
    """Render and write ``$HERMES_HOME/config.yaml``. Returns the path written."""
    target_home = home or hermes_home()
    target_home.mkdir(parents=True, exist_ok=True)
    path = target_home / "config.yaml"
    document = render_config(config, autonomy=autonomy, terminal=terminal)
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def build_command(
    decision: Decision,
    text: str,
    skills: list[str] | None = None,
    oneshot: bool = True,
    quiet: bool = True,
    executable: str = "hermes",
) -> list[str]:
    """Assemble the ``hermes chat`` argv for a routed run.

    Flags used (verified against the Hermes CLI reference, repo v0.21.0):
      -q/--query    seed the session with a prompt
      --oneshot     answer and exit instead of staying interactive
      -Q/--quiet    programmatic mode, suppress cosmetic output
      -m/--model    override the model for this run
      -s/--skills   preload skills
    """
    command = [executable, "chat", "--query", text, "--model", decision.model_ref]
    if oneshot:
        command.append("--oneshot")
    if quiet:
        command.append("--quiet")
    for skill in skills or []:
        command.extend(["--skills", skill])
    return command
