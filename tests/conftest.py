"""Shared fixtures.

No test in this suite may reach the network or use a real credential. The
`isolated_env` fixture below enforces the second half of that by wiping every
PFA_* variable from the environment before each test.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ambient configuration so tests never inherit a developer's setup."""
    for name in (
        "PFA_CONFIG",
        "PFA_LOG_DIR",
        "PFA_LOCAL_BASE_URL",
        "PFA_LOCAL_API_KEY",
        "PFA_CLOUD_BASE_URL",
        "PFA_CLOUD_API_KEY",
        "PFA_SKILLS_DIR",
        "HERMES_HOME",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def policy_text() -> str:
    """A minimal but complete policy, independent of the shipped one."""
    return textwrap.dedent(
        """
        version: 1
        providers:
          local:
            base_url: "${TEST_LOCAL_URL:-http://localhost:11434/v1}"
            api_key_env: TEST_LOCAL_KEY
            default_model: "gemma4:e4b"
            cost_per_1m_input_tokens: 0.0
            cost_per_1m_output_tokens: 0.0
          cloud:
            base_url: "https://example.invalid/v1"
            api_key_env: TEST_CLOUD_KEY
            default_model: "vendor/big-model"
            cost_per_1m_input_tokens: 3.0
            cost_per_1m_output_tokens: 15.0
        default_task: simple
        routes:
          simple:
            provider: local
            model: "gemma4:e2b"
          research:
            provider: local
            model: null
          coding:
            provider: cloud
            model: null
        classification:
          rules:
            - task: coding
              keywords: [implement, refactor]
            - task: research
              keywords: [research, compare]
        """
    ).strip()


@pytest.fixture
def policy_file(tmp_path: Path, policy_text: str) -> Path:
    path = tmp_path / "routing.yaml"
    path.write_text(policy_text, encoding="utf-8")
    return path


def write_skill(
    root: Path,
    name: str,
    category: str = "fde",
    version: str = "1.0.0",
    description: str = "A throwaway procedure.",
    body: str = "# Procedure\n\nDo the thing, then check it.\n",
    frontmatter_name: str | None = None,
) -> Path:
    """Create one SKILL.md under ``root``. Returns the file written."""
    directory = root / category / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    path.write_text(
        "---\n"
        f"name: {frontmatter_name or name}\n"
        f"description: {description}\n"
        f"version: {version}\n"
        "metadata:\n"
        "  hermes:\n"
        "    tags: [test]\n"
        f"    category: {category}\n"
        "---\n\n" + body,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def skills_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway skill library, independent of the one this repository ships."""
    root = tmp_path / "skills"
    write_skill(root, "alpha-procedure")
    write_skill(root, "beta-procedure")
    monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
    return root


@pytest.fixture
def policy_with_skills(tmp_path: Path, policy_text: str) -> Path:
    """The throwaway policy, with procedures attached to two of its routes.

    Kept separate from `policy_file` so the routing tests stay independent of
    whether a skill library exists at all.
    """
    text = policy_text
    for anchor, attached in (
        ("  research:\n    provider: local\n    model: null", "[alpha-procedure]"),
        ("  coding:\n    provider: cloud\n    model: null", "[alpha-procedure, beta-procedure]"),
    ):
        # Assert rather than replace-and-hope: a silently unmatched anchor would
        # produce a policy with no skills and tests that pass for the wrong reason.
        assert anchor in text, f"policy_text no longer contains:\n{anchor}"
        text = text.replace(anchor, f"{anchor}\n    skills: {attached}")

    path = tmp_path / "routing-with-skills.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard-block outbound probing.

    `pfa doctor` reaches provider endpoints by design. In tests that must never
    happen: a suite that touches the network is slow, flaky, and dependent on
    whoever is running it. The probe seam is stubbed to a deterministic answer;
    a test that wants to exercise probing patches it back explicitly.
    """
    monkeypatch.setattr(
        "pfa.doctor._probe_endpoint",
        lambda base_url, timeout=3.0: (False, "probing disabled in tests"),
    )
