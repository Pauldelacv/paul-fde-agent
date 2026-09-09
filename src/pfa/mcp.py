"""MCP connector declarations and their rendering into the Hermes config.

Hermes owns the MCP client: transports, the handshake, tool discovery,
registration and filtering. This module does not reimplement any of it. It owns
the *policy* — which servers the agent may reach, which of their tools it may
see, and which credentials each one needs — and renders that policy into the
``mcp_servers`` block Hermes reads.

Schema verified against the Hermes MCP guide on 2026-09-09; see
docs/verified-facts.md.

Why ``${VAR}`` is NOT expanded here
-----------------------------------
``config/routing.yaml`` is expanded at load time, because we act on its values
ourselves. ``config/mcp.yaml`` is the opposite case: the reference must survive
into ``$HERMES_HOME/config.yaml`` so that Hermes resolves it at connect time and
the rendered file stays safe to read, diff and back up. Expanding it here would
write the credential to disk.

That passthrough has a documented failure mode. Hermes keeps an unset ``${VAR}``
**verbatim** and only logs a warning, so a server whose key is missing connects
with the literal text ``${LEMLIST_API_KEY}`` as its credential and fails with a
401 that reads like a wrong key rather than an absent one. Two guards:
:meth:`McpServer.missing_env` reports it before a connection is attempted, and
validation refuses a server that references a variable it does not declare —
because an undeclared reference is one nothing checks.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

DEFAULT_MCP_PATH = Path("config/mcp.yaml")

#: ``${VAR}`` as Hermes resolves it. ``${env:VAR}`` is the Cursor-style spelling
#: Hermes also accepts; both are recognised so neither escapes the env check.
_ENV_REFERENCE = re.compile(r"\$\{(?:env:)?([A-Za-z_][A-Za-z0-9_]*)\}")

#: A server name becomes a YAML key and a CLI argument.
_NAME = re.compile(r"\A[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")

TRANSPORTS = ("http", "stdio")


def _references(value: Any) -> set[str]:
    """Every environment variable named by a ``${VAR}`` anywhere inside ``value``."""
    if isinstance(value, str):
        return set(_ENV_REFERENCE.findall(value))
    if isinstance(value, dict):
        return set().union(*(_references(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_references(v) for v in value)) if value else set()
    return set()


@dataclass(frozen=True)
class McpServer:
    """One declared MCP server, and what it needs in order to work."""

    name: str
    transport: str
    enabled: bool = True
    description: str = ""
    url: str | None = None
    headers: dict[str, str] | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    requires_env: tuple[str, ...] = ()
    tools_include: tuple[str, ...] = ()
    tools_exclude: tuple[str, ...] = ()
    connect_timeout: int | None = None
    timeout: int | None = None

    @property
    def target(self) -> str:
        """Where this server actually is — a URL, or the command that starts it."""
        if self.transport == "http":
            return self.url or ""
        return " ".join([self.command or "", *self.args]).strip()

    def missing_env(self, environ: dict[str, str] | None = None) -> tuple[str, ...]:
        """Declared variables that are unset or empty, in declaration order.

        Empty counts as missing: an empty string substituted into an
        ``X-API-Key`` header is a credential that fails, not a credential.
        """
        env = os.environ if environ is None else environ
        return tuple(name for name in self.requires_env if not env.get(name))

    def to_hermes(self) -> dict[str, Any]:
        """The ``mcp_servers.<name>`` value Hermes reads.

        Only keys Hermes documents are emitted, and only when set — a config
        full of nulls invites the reader to wonder which of them are meaningful.
        """
        document: dict[str, Any] = {}
        if self.transport == "http":
            document["url"] = self.url
            if self.headers:
                document["headers"] = dict(self.headers)
        else:
            document["command"] = self.command
            if self.args:
                document["args"] = list(self.args)
            if self.env:
                document["env"] = dict(self.env)
        if self.connect_timeout is not None:
            document["connect_timeout"] = self.connect_timeout
        if self.timeout is not None:
            document["timeout"] = self.timeout
        tools: dict[str, list[str]] = {}
        if self.tools_include:
            tools["include"] = list(self.tools_include)
        if self.tools_exclude:
            tools["exclude"] = list(self.tools_exclude)
        if tools:
            document["tools"] = tools
        return document

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "transport": self.transport,
            "target": self.target,
            "description": self.description,
            "requires_env": list(self.requires_env),
            "tools_include": list(self.tools_include),
            "tools_exclude": list(self.tools_exclude),
        }


@dataclass(frozen=True)
class McpCatalogue:
    """The validated set of declared MCP servers."""

    servers: tuple[McpServer, ...] = ()
    source_path: Path | None = None

    @property
    def enabled(self) -> tuple[McpServer, ...]:
        return tuple(server for server in self.servers if server.enabled)

    def get(self, name: str) -> McpServer | None:
        return next((server for server in self.servers if server.name == name), None)

    def to_hermes(self) -> dict[str, Any]:
        """The whole ``mcp_servers`` block, disabled servers excluded.

        A disabled server is omitted rather than emitted with ``enabled: false``.
        Hermes honours the flag either way; leaving it out keeps the rendered
        file a statement of what the agent can reach, which is the question
        someone reviewing it is asking.
        """
        return {server.name: server.to_hermes() for server in self.enabled}


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping, got {type(value).__name__}.")
    return value


def _string_map(value: Any, where: str) -> dict[str, str]:
    block = _require_mapping(value, where)
    for key, item in block.items():
        if not isinstance(item, str):
            raise ConfigError(
                f"`{where}.{key}` must be a string. Use `${{VAR}}` to reference a "
                f"credential by name; never inline the value."
            )
    return {str(k): v for k, v in block.items()}


def _string_list(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"`{where}` must be a list of strings.")
    return tuple(value)


def _parse_server(name: Any, spec: dict[str, Any]) -> McpServer:
    # YAML 1.1 resolves bare `on`, `off`, `yes`, `no`, `true` and `false` to
    # booleans, so a server innocently named `off:` arrives here as False. Say
    # so, rather than failing on a type nobody wrote.
    if not isinstance(name, str):
        raise ConfigError(
            f"MCP server name {name!r} was parsed as {type(name).__name__}, not text. "
            f"YAML reads bare `on`, `off`, `yes`, `no`, `true` and `false` as booleans — "
            f"quote the name to keep it a string."
        )
    if not _NAME.match(name):
        raise ConfigError(
            f"MCP server name {name!r} must be lowercase words joined by hyphens or underscores."
        )

    transport = spec.get("transport")
    if transport not in TRANSPORTS:
        raise ConfigError(
            f"`servers.{name}.transport` is {transport!r}; must be one of {', '.join(TRANSPORTS)}."
        )

    url = spec.get("url")
    command = spec.get("command")
    if transport == "http" and not url:
        raise ConfigError(f"`servers.{name}` is transport http and must define `url`.")
    if transport == "stdio" and not command:
        raise ConfigError(f"`servers.{name}` is transport stdio and must define `command`.")
    if transport == "http" and command:
        raise ConfigError(
            f"`servers.{name}` declares both `url` and `command`. A server is reached "
            f"one way or the other; pick the transport that matches."
        )

    tools = _require_mapping(spec.get("tools") or {}, f"`servers.{name}.tools`")
    server = McpServer(
        name=name,
        transport=transport,
        enabled=bool(spec.get("enabled", True)),
        description=str(spec.get("description", "")).strip(),
        url=url,
        headers=_string_map(spec.get("headers") or {}, f"servers.{name}.headers") or None,
        command=command,
        args=_string_list(spec.get("args"), f"servers.{name}.args"),
        env=_string_map(spec.get("env") or {}, f"servers.{name}.env") or None,
        requires_env=_string_list(spec.get("requires_env"), f"servers.{name}.requires_env"),
        tools_include=_string_list(tools.get("include"), f"servers.{name}.tools.include"),
        tools_exclude=_string_list(tools.get("exclude"), f"servers.{name}.tools.exclude"),
        connect_timeout=spec.get("connect_timeout"),
        timeout=spec.get("timeout"),
    )

    # Every `${VAR}` the server references must be declared. An undeclared
    # reference is one no check covers, and Hermes passes an unset one through
    # verbatim — so it would reach the network as a literal credential string.
    undeclared = sorted(_references(server.to_hermes()) - set(server.requires_env))
    if undeclared:
        raise ConfigError(
            f"`servers.{name}` references {', '.join(undeclared)} but does not list "
            f"them in `requires_env`. Hermes passes an unset ${{VAR}} through verbatim, "
            f"so an undeclared reference fails as a bad credential rather than a missing "
            f"one. Add it to `requires_env`."
        )
    return server


def load_mcp_config(path: str | Path | None = None) -> McpCatalogue:
    """Read and validate the MCP connector declarations.

    A missing file at the *default* location yields an empty catalogue: MCP
    connectors are additive, and an agent with none is a working agent. A path
    given explicitly — by argument or ``$PFA_MCP_CONFIG`` — must exist, because
    naming a file you meant to load and having it silently ignored is the
    failure this project exists not to have.
    """
    explicit = path or os.environ.get("PFA_MCP_CONFIG")
    config_path = Path(explicit or DEFAULT_MCP_PATH)

    if not config_path.is_file():
        if explicit:
            raise ConfigError(
                f"MCP connector file not found at {config_path}. "
                f"Correct --mcp-config / $PFA_MCP_CONFIG, or remove it to run without connectors."
            )
        return McpCatalogue()

    try:
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML: {exc}") from exc

    if parsed is None:
        return McpCatalogue(source_path=config_path)

    raw = _require_mapping(parsed, str(config_path))
    version = raw.get("version")
    if version != 1:
        raise ConfigError(
            f"Unsupported MCP connector version {version!r}; this build understands version 1."
        )

    block = _require_mapping(raw.get("servers") or {}, "`servers`")
    servers = tuple(
        _parse_server(name, _require_mapping(spec, f"`servers.{name}`"))
        for name, spec in block.items()
    )
    return McpCatalogue(servers=servers, source_path=config_path)
