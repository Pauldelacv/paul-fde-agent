"""Configuration loading, environment substitution and validation."""

from __future__ import annotations

import pytest

from pfa.config import load_config, substitute_env
from pfa.errors import ConfigError


class TestEnvSubstitution:
    def test_expands_set_variable(self):
        assert substitute_env("${FOO}", {"FOO": "bar"}) == "bar"

    def test_uses_default_when_unset(self):
        assert substitute_env("${MISSING:-fallback}", {}) == "fallback"

    def test_set_variable_wins_over_default(self):
        assert substitute_env("${FOO:-fallback}", {"FOO": "actual"}) == "actual"

    def test_unset_without_default_becomes_empty(self):
        # Must not raise: doctor has to stay able to *report* the omission.
        assert substitute_env("${MISSING}", {}) == ""

    def test_recurses_into_nested_structures(self):
        source = {"a": ["${FOO}", {"b": "${FOO}"}]}
        assert substitute_env(source, {"FOO": "x"}) == {"a": ["x", {"b": "x"}]}

    def test_leaves_non_strings_untouched(self):
        assert substitute_env({"n": 1, "f": 1.5, "b": True}, {}) == {"n": 1, "f": 1.5, "b": True}


class TestLoading:
    def test_loads_valid_policy(self, policy_file):
        config = load_config(policy_file)
        assert config.version == 1
        assert set(config.providers) == {"local", "cloud"}
        assert set(config.routes) == {"simple", "research", "coding"}
        assert len(config.rules) == 2

    def test_applies_env_substitution_to_base_url(self, policy_file, monkeypatch):
        monkeypatch.setenv("TEST_LOCAL_URL", "http://ollama:11434/v1")
        config = load_config(policy_file)
        assert config.providers["local"].base_url == "http://ollama:11434/v1"

    def test_falls_back_to_default_base_url(self, policy_file):
        config = load_config(policy_file)
        assert config.providers["local"].base_url == "http://localhost:11434/v1"

    def test_null_model_means_provider_default(self, policy_file):
        config = load_config(policy_file)
        assert config.routes["research"].model is None
        assert config.providers["local"].default_model == "gemma4:e4b"

    def test_local_provider_detected_by_zero_cost(self, policy_file):
        config = load_config(policy_file)
        assert config.providers["local"].is_local is True
        assert config.providers["cloud"].is_local is False

    def test_api_key_read_from_named_env_var(self, policy_file, monkeypatch):
        monkeypatch.setenv("TEST_CLOUD_KEY", "value-from-env")
        config = load_config(policy_file)
        assert config.providers["cloud"].api_key({"TEST_CLOUD_KEY": "value-from-env"}) == (
            "value-from-env"
        )

    def test_missing_key_returns_none_not_empty_string(self, policy_file):
        config = load_config(policy_file)
        assert config.providers["cloud"].api_key({}) is None


class TestValidationErrors:
    """Every failure must name the offending key and what to do about it."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nope.yaml")

    def test_invalid_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("version: 1\n  bad: [indent", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid YAML"):
            load_config(path)

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ConfigError, match="empty"):
            load_config(path)

    def test_wrong_version(self, tmp_path):
        path = tmp_path / "v2.yaml"
        path.write_text("version: 2\nproviders: {}\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="Unsupported policy version"):
            load_config(path)

    def test_route_referencing_unknown_provider(self, tmp_path, policy_text):
        path = tmp_path / "p.yaml"
        path.write_text(policy_text.replace("provider: cloud", "provider: ghost"), encoding="utf-8")
        with pytest.raises(ConfigError, match="not a defined provider"):
            load_config(path)

    def test_rule_referencing_unknown_route(self, tmp_path, policy_text):
        path = tmp_path / "p.yaml"
        path.write_text(
            policy_text.replace("- task: coding", "- task: nonexistent"), encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="no matching route"):
            load_config(path)

    def test_default_task_must_have_a_route(self, tmp_path, policy_text):
        path = tmp_path / "p.yaml"
        path.write_text(
            policy_text.replace("default_task: simple", "default_task: ghost"), encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="default_task"):
            load_config(path)

    def test_provider_missing_required_key(self, tmp_path, policy_text):
        path = tmp_path / "p.yaml"
        path.write_text(
            policy_text.replace("    api_key_env: TEST_LOCAL_KEY\n", ""), encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="missing required key `api_key_env`"):
            load_config(path)

    def test_provider_cost_must_be_numeric(self, tmp_path, policy_text):
        path = tmp_path / "p.yaml"
        path.write_text(
            policy_text.replace(
                "cost_per_1m_input_tokens: 3.0", 'cost_per_1m_input_tokens: "free"'
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="must be int or float"):
            load_config(path)


class TestShippedPolicy:
    """The policy committed to the repository must itself be valid."""

    def test_shipped_policy_loads(self, repo_root):
        config = load_config(repo_root / "config" / "routing.yaml")
        assert config.default_task in config.routes
        assert "local" in config.providers and "cloud" in config.providers

    def test_shipped_policy_has_no_inline_credentials(self, repo_root):
        body = (repo_root / "config" / "routing.yaml").read_text(encoding="utf-8")
        assert "api_key:" not in body, "policy must reference key NAMES, never values"
        assert "sk-" not in body


class TestRouteSkills:
    def test_skills_default_to_empty(self, policy_file):
        assert load_config(policy_file).routes["simple"].skills == ()

    def test_skills_are_read_in_policy_order(self, policy_with_skills):
        assert load_config(policy_with_skills).routes["coding"].skills == (
            "alpha-procedure",
            "beta-procedure",
        )

    def test_a_non_list_is_rejected_with_the_key_named(self, tmp_path, policy_text):
        broken = tmp_path / "broken.yaml"
        broken.write_text(
            policy_text.replace(
                "  simple:\n    provider: local",
                "  simple:\n    skills: nope\n    provider: local",
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="`routes.simple.skills` must be a list"):
            load_config(broken)

    def test_the_loader_does_not_check_the_filesystem(self, tmp_path, policy_text):
        # The policy is a document about intent. Whether a named skill exists is
        # a question for `pfa doctor` and for the runner, not for the parser.
        policy = tmp_path / "unknown-skill.yaml"
        policy.write_text(
            policy_text.replace(
                "  simple:\n    provider: local",
                "  simple:\n    skills: [does-not-exist]\n    provider: local",
            ),
            encoding="utf-8",
        )
        assert load_config(policy).routes["simple"].skills == ("does-not-exist",)
