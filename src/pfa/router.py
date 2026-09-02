"""Task classification and model resolution.

The router answers: *given this request, which backend and model should run it?*

It is deliberately a pure function of (text, policy). No network, no model call,
no hidden state — so it is trivially testable and its decisions can be explained
to the operator before a single token is spent. `pfa route` prints the decision
without executing anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config, Provider
from .errors import RoutingError


@dataclass(frozen=True)
class Decision:
    """The outcome of routing, including *why* — never present a guess as a fact."""

    task: str
    provider: Provider
    model: str
    #: How the task category was determined: "explicit", "keyword" or "default".
    basis: str
    #: The keyword that matched, when basis == "keyword".
    matched_keyword: str | None = None
    #: Procedures the policy attaches to this category, in policy order.
    skills: tuple[str, ...] = ()

    @property
    def model_ref(self) -> str:
        """The ``provider/model`` reference passed to ``hermes chat --model``."""
        return f"{self.provider.name}/{self.model}"

    def explain(self) -> str:
        if self.basis == "explicit":
            why = "task category given explicitly"
        elif self.basis == "keyword":
            why = f"matched keyword {self.matched_keyword!r}"
        else:
            why = "no rule matched; fell back to default_task"
        tier = "local (no per-token cost)" if self.provider.is_local else "cloud (billed)"
        line = f"{self.task} -> {self.model_ref} [{tier}] ({why})"
        if self.skills:
            line += f" + skills: {', '.join(self.skills)}"
        return line


def _keyword_matches(text: str, keyword: str) -> bool:
    """Case-insensitive match on word boundaries.

    Boundaries matter: without them "error" matches inside "terror" and, more
    plausibly here, "adr" matches inside "quadrant".
    """
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text, re.IGNORECASE) is not None


def classify(text: str, config: Config) -> tuple[str, str, str | None]:
    """Map free-form task text to a task category.

    Returns ``(task, basis, matched_keyword)``. Rules are evaluated in policy
    order and the first match wins, so ordering in the YAML is meaningful:
    put the most specific categories first.
    """
    for rule in config.rules:
        for keyword in rule.keywords:
            if _keyword_matches(text, keyword):
                return rule.task, "keyword", keyword
    return config.default_task, "default", None


def route(
    text: str,
    config: Config,
    task: str | None = None,
    auto_skills: bool = True,
) -> Decision:
    """Resolve free-form task text (or an explicit category) to a Decision.

    ``auto_skills=False`` drops the procedures the policy attaches to the
    category. The category itself is unaffected: suppressing a skill must never
    quietly change which model runs the task.
    """
    if task:
        if task not in config.routes:
            known = ", ".join(sorted(config.routes))
            raise RoutingError(f"Unknown task category {task!r}. Available: {known}.")
        category, basis, keyword = task, "explicit", None
    else:
        category, basis, keyword = classify(text, config)

    selected = config.routes[category]
    provider = config.provider_for(selected.provider)
    model = selected.model or provider.default_model

    return Decision(
        task=category,
        provider=provider,
        model=model,
        basis=basis,
        matched_keyword=keyword,
        skills=selected.skills if auto_skills else (),
    )


def estimate_cost(decision: Decision, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD cost of a run.

    Accuracy is bounded by the pricing figures in the policy file, which the
    operator maintains. Treat the number as an order of magnitude, not a bill.
    """
    provider = decision.provider
    return (
        input_tokens / 1_000_000 * provider.cost_per_1m_input_tokens
        + output_tokens / 1_000_000 * provider.cost_per_1m_output_tokens
    )
