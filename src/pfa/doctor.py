"""Environment healthcheck.

``pfa doctor`` is the first thing to run on a new machine and the first thing to
run when something breaks. It reports facts, separates them from advice, and
never guesses: a check that cannot be performed reports SKIP, not PASS.
"""

from __future__ import annotations

import json
import os
import stat
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import Config, load_config
from .errors import ConfigError
from .hermes import find_hermes, hermes_home, hermes_version

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    remedy: str = ""


def _probe_endpoint(base_url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """GET the endpoint root. Returns (reachable, detail)."""
    url = base_url.rstrip("/")
    # Ollama's OpenAI-compatible surface lives at /v1; its health root is one level up.
    probe = url[: -len("/v1")] if url.endswith("/v1") else url
    try:
        with urllib.request.urlopen(probe, timeout=timeout) as response:  # noqa: S310
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        # A 4xx still proves something is listening and speaking HTTP.
        return True, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, str(getattr(exc, "reason", exc))


def check_config(config_path: str | None = None) -> tuple[list[Check], Config | None]:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        return [Check("routing policy", FAIL, str(exc), "Fix config/routing.yaml.")], None

    detail = (
        f"{config.source_path} — {len(config.providers)} providers, "
        f"{len(config.routes)} routes, {len(config.rules)} rules"
    )
    return [Check("routing policy", PASS, detail)], config


def check_runtime() -> list[Check]:
    executable = find_hermes()
    if not executable:
        return [
            Check(
                "hermes runtime",
                FAIL,
                "not found on PATH",
                "pip install 'paul-fde-agent[hermes]'  (or run: make up)",
            )
        ]
    version = hermes_version()
    return [
        Check(
            "hermes runtime",
            PASS,
            f"{executable} ({version or 'version unreported'})",
        )
    ]


def check_providers(config: Config) -> list[Check]:
    checks: list[Check] = []
    for name, provider in sorted(config.providers.items()):
        key = provider.api_key(os.environ)
        if not key:
            checks.append(
                Check(
                    f"provider:{name} credentials",
                    WARN,
                    f"${provider.api_key_env} is not set",
                    f"Add {provider.api_key_env} to your .env (copy .env.example if you have not).",
                )
            )
        elif key.startswith("REPLACE_ME"):
            checks.append(
                Check(
                    f"provider:{name} credentials",
                    FAIL,
                    f"${provider.api_key_env} still holds the placeholder value",
                    f"Replace {provider.api_key_env} in .env with a real key.",
                )
            )
        else:
            checks.append(
                Check(f"provider:{name} credentials", PASS, f"${provider.api_key_env} is set")
            )

        reachable, detail = _probe_endpoint(provider.base_url)
        checks.append(
            Check(
                f"provider:{name} endpoint",
                PASS if reachable else WARN,
                f"{provider.base_url} — {detail}",
                ""
                if reachable
                else (
                    "Start the backend (`ollama serve`, or `make up`) or correct base_url. "
                    "A cloud endpoint may also simply refuse unauthenticated probes."
                ),
            )
        )
    return checks


def check_secret_hygiene(root: Path | None = None) -> list[Check]:
    """Confirm the repository is not about to leak credentials."""
    base = root or Path.cwd()
    checks: list[Check] = []

    gitignore = base / ".gitignore"
    if gitignore.is_file():
        body = gitignore.read_text(encoding="utf-8")
        missing = [p for p in (".env", "*.db", "private/", "var/") if p not in body]
        checks.append(
            Check(
                "gitignore covers secrets",
                PASS if not missing else FAIL,
                "all critical patterns present"
                if not missing
                else f"missing patterns: {', '.join(missing)}",
                "" if not missing else "Restore the patterns in .gitignore.",
            )
        )
    else:
        checks.append(
            Check(
                "gitignore covers secrets",
                FAIL,
                ".gitignore is absent",
                "Create a .gitignore — this repository is meant to be public.",
            )
        )

    env_file = base / ".env"
    if not env_file.is_file():
        checks.append(
            Check("local .env", SKIP, "no .env present", "cp .env.example .env && chmod 600 .env")
        )
    else:
        mode = stat.S_IMODE(env_file.stat().st_mode)
        too_open = bool(mode & 0o077)
        checks.append(
            Check(
                "local .env permissions",
                WARN if too_open else PASS,
                f"mode {mode:04o}",
                "chmod 600 .env" if too_open else "",
            )
        )
    return checks


def check_hermes_home() -> list[Check]:
    home = hermes_home()
    if not home.exists():
        return [
            Check("hermes home", SKIP, f"{home} does not exist yet", "pfa hermes-config --write")
        ]
    config_file = home / "config.yaml"
    return [
        Check(
            "hermes home",
            PASS if config_file.is_file() else WARN,
            f"{home} — config.yaml {'present' if config_file.is_file() else 'missing'}",
            "" if config_file.is_file() else "pfa hermes-config --write",
        )
    ]


def run_all(config_path: str | None = None) -> list[Check]:
    checks, config = check_config(config_path)
    checks += check_runtime()
    if config is not None:
        checks += check_providers(config)
    checks += check_hermes_home()
    checks += check_secret_hygiene()
    return checks


def worst_status(checks: list[Check]) -> str:
    for level in (FAIL, WARN, PASS):
        if any(c.status == level for c in checks):
            return level
    return SKIP


def to_json(checks: list[Check]) -> str:
    return json.dumps([c.__dict__ for c in checks], indent=2)
