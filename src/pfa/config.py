"""Loading and validation of the routing policy.

The policy is plain YAML with `${VAR}` / `${VAR:-default}` substitution applied
at load time. Secrets are never stored in it: a provider names the *environment
variable* holding its key (`api_key_env`) and the value is resolved separately,
only at the moment it is needed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

# ${VAR} or ${VAR:-default}
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

DEFAULT_CONFIG_PATH = Path("config/routing.yaml")

# Keys a provider block must define, with the type each must have.
_PROVIDER_REQUIRED: dict[str, type | tuple[type, ...]] = {
    "base_url": str,
    "api_key_env": str,
    "default_model": str,
    "cost_per_1m_input_tokens": (int, float),
    "cost_per_1m_output_tokens": (int, float),
}


def substitute_env(value: Any, environ: dict[str, str] | None = None) -> Any:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` in strings.

    An unset variable with no default expands to an empty string rather than
    raising: a policy file must stay loadable so that ``pfa doctor`` can *report*
    the missing variable instead of crashing before it gets the chance.
    """
    env = os.environ if environ is None else environ

    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: env.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: substitute_env(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_env(v, env) for v in value]
    return value


@dataclass(frozen=True)
class Provider:
    """A model backend: an OpenAI-compatible endpoint plus its cost profile."""

    name: str
    base_url: str
    api_key_env: str
    default_model: str
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float

    @property
    def is_local(self) -> bool:
        return self.cost_per_1m_input_tokens == 0.0 and self.cost_per_1m_output_tokens == 0.0

    def api_key(self, environ: dict[str, str] | None = None) -> str | None:
        env = os.environ if environ is None else environ
        return env.get(self.api_key_env) or None


@dataclass(frozen=True)
class Route:
    """A task category bound to a provider and (optionally) a specific model."""

    task: str
    provider: str
    model: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Rule:
    """One keyword rule mapping task text to a task category."""

    task: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    """The validated routing policy."""

    version: int
    providers: dict[str, Provider]
    routes: dict[str, Route]
    rules: tuple[Rule, ...]
    default_task: str
    source_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def provider_for(self, name: str) -> Provider:
        try:
            return self.providers[name]
        except KeyError:
            known = ", ".join(sorted(self.providers))
            raise ConfigError(f"Unknown provider {name!r}. Defined providers: {known}.") from None


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping, got {type(value).__name__}.")
    return value


def _parse_providers(raw: dict[str, Any]) -> dict[str, Provider]:
    block = _require_mapping(raw.get("providers"), "`providers`")
    if not block:
        raise ConfigError("`providers` is empty; define at least one model backend.")

    providers: dict[str, Provider] = {}
    for name, spec in block.items():
        spec = _require_mapping(spec, f"`providers.{name}`")
        for key, expected in _PROVIDER_REQUIRED.items():
            if key not in spec:
                raise ConfigError(f"`providers.{name}` is missing required key `{key}`.")
            if not isinstance(spec[key], expected):
                type_name = (
                    expected.__name__
                    if isinstance(expected, type)
                    else " or ".join(t.__name__ for t in expected)
                )
                raise ConfigError(
                    f"`providers.{name}.{key}` must be {type_name}, got {type(spec[key]).__name__}."
                )
        if not spec["base_url"]:
            raise ConfigError(
                f"`providers.{name}.base_url` resolved to an empty string. "
                f"The environment variable it references is probably unset."
            )
        providers[name] = Provider(
            name=name,
            base_url=spec["base_url"],
            api_key_env=spec["api_key_env"],
            default_model=spec["default_model"],
            cost_per_1m_input_tokens=float(spec["cost_per_1m_input_tokens"]),
            cost_per_1m_output_tokens=float(spec["cost_per_1m_output_tokens"]),
        )
    return providers


def _parse_routes(raw: dict[str, Any], providers: dict[str, Provider]) -> dict[str, Route]:
    block = _require_mapping(raw.get("routes"), "`routes`")
    if not block:
        raise ConfigError("`routes` is empty; define at least one task category.")

    routes: dict[str, Route] = {}
    for task, spec in block.items():
        spec = _require_mapping(spec, f"`routes.{task}`")
        provider = spec.get("provider")
        if not provider:
            raise ConfigError(f"`routes.{task}` is missing required key `provider`.")
        if provider not in providers:
            known = ", ".join(sorted(providers))
            raise ConfigError(
                f"`routes.{task}.provider` is {provider!r}, which is not a defined "
                f"provider. Defined providers: {known}."
            )
        routes[task] = Route(
            task=task,
            provider=provider,
            model=spec.get("model") or None,
            description=spec.get("description", ""),
        )
    return routes


def _parse_rules(raw: dict[str, Any], routes: dict[str, Route]) -> tuple[Rule, ...]:
    classification = raw.get("classification") or {}
    classification = _require_mapping(classification, "`classification`")
    entries = classification.get("rules") or []
    if not isinstance(entries, list):
        raise ConfigError("`classification.rules` must be a list.")

    rules: list[Rule] = []
    for index, entry in enumerate(entries):
        entry = _require_mapping(entry, f"`classification.rules[{index}]`")
        task = entry.get("task")
        if not task:
            raise ConfigError(f"`classification.rules[{index}]` is missing `task`.")
        if task not in routes:
            known = ", ".join(sorted(routes))
            raise ConfigError(
                f"`classification.rules[{index}].task` is {task!r}, which has no "
                f"matching route. Defined routes: {known}."
            )
        keywords = entry.get("keywords") or []
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise ConfigError(
                f"`classification.rules[{index}].keywords` must be a list of strings."
            )
        rules.append(Rule(task=task, keywords=tuple(k.lower() for k in keywords)))
    return tuple(rules)


def load_config(
    path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Config:
    """Read, expand and validate the routing policy.

    Raises :class:`ConfigError` with an actionable message on any problem.
    """
    config_path = Path(path or os.environ.get("PFA_CONFIG") or DEFAULT_CONFIG_PATH)
    if not config_path.is_file():
        raise ConfigError(
            f"Routing policy not found at {config_path}. "
            f"Pass --config, set PFA_CONFIG, or run from the repository root."
        )

    try:
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML: {exc}") from exc

    if parsed is None:
        raise ConfigError(f"{config_path} is empty.")

    raw = substitute_env(_require_mapping(parsed, str(config_path)), environ)

    version = raw.get("version")
    if version != 1:
        raise ConfigError(
            f"Unsupported policy version {version!r}; this build understands version 1."
        )

    providers = _parse_providers(raw)
    routes = _parse_routes(raw, providers)
    rules = _parse_rules(raw, routes)

    default_task = raw.get("default_task")
    if not default_task:
        raise ConfigError("`default_task` is required.")
    if default_task not in routes:
        known = ", ".join(sorted(routes))
        raise ConfigError(
            f"`default_task` is {default_task!r}, which has no matching route. "
            f"Defined routes: {known}."
        )

    return Config(
        version=version,
        providers=providers,
        routes=routes,
        rules=rules,
        default_task=default_task,
        source_path=config_path,
        raw=raw,
    )
