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
