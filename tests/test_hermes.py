# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""The Hermes integration layer: config rendering, autonomy, argv construction."""

from __future__ import annotations

from pathlib import Path

import yaml

from pfa.config import load_config
from pfa.hermes import (
    AUTONOMY_LEVELS,
    DENY_GLOBS,
    build_command,
    render_config,
    write_config,
)
from pfa.router import route


class TestRenderedConfig:
    def test_names_every_provider(self, policy_file):
        document = render_config(load_config(policy_file))
        assert set(document["providers"]) == {"local", "cloud"}

    def test_default_model_comes_from_default_task(self, policy_file):
        document = render_config(load_config(policy_file))
        assert document["model"] == "local/gemma4:e2b"

    def test_api_keys_are_references_never_values(self, policy_file, monkeypatch):
        # Even with a real-looking key in the environment, it must not be inlined.
        monkeypatch.setenv("TEST_CLOUD_KEY", "sk-thisisaverysecretvalue123456")
        rendered = yaml.safe_dump(render_config(load_config(policy_file)))
        assert "sk-thisisaverysecretvalue123456" not in rendered
        assert "${TEST_CLOUD_KEY}" in rendered

    def test_deny_globs_are_present(self, policy_file):
        document = render_config(load_config(policy_file))
        assert set(DENY_GLOBS).issubset(set(document["approvals"]["deny"]))

    def test_irreversible_operations_are_denied(self, policy_file):
        deny = render_config(load_config(policy_file))["approvals"]["deny"]
        joined = " ".join(deny)
        for fragment in ("rm -rf /", "DROP DATABASE", "git push --force", "mkfs"):
            assert fragment in joined

    def test_written_file_is_valid_yaml_and_has_no_secrets(
        self, policy_file, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("TEST_CLOUD_KEY", "sk-anothersecretvalue0987654321")
        path = write_config(load_config(policy_file), home=tmp_path / "hermes")
        body = path.read_text(encoding="utf-8")
        assert yaml.safe_load(body)["model"].startswith("local/")
        assert "sk-anothersecretvalue0987654321" not in body


class TestAutonomyLevels:
    def test_four_levels_numbered_one_to_four(self):
        assert sorted(level.number for level in AUTONOMY_LEVELS.values()) == [1, 2, 3, 4]

    def test_read_and_propose_require_manual_approval(self):
        assert AUTONOMY_LEVELS["read"].approvals_mode == "manual"
        assert AUTONOMY_LEVELS["propose"].approvals_mode == "manual"

    def test_no_level_ever_permits_unattended_destructive_actions(self):
        # This is the invariant the whole permission model rests on.
        assert all(level.unattended_mode == "deny" for level in AUTONOMY_LEVELS.values())

    def test_no_level_disables_approvals_entirely(self):
        assert all(level.approvals_mode != "off" for level in AUTONOMY_LEVELS.values())

    def test_level_selection_changes_rendered_config(self, policy_file):
        config = load_config(policy_file)
        assert render_config(config, autonomy="read")["approvals"]["mode"] == "manual"
        assert render_config(config, autonomy="execute")["approvals"]["mode"] == "smart"


class TestCommandConstruction:
    def test_uses_verified_flags(self, policy_file):
        config = load_config(policy_file)
        command = build_command(route("implement it", config), "implement it")
        assert command[:2] == ["hermes", "chat"]
        for flag in ("--query", "--model", "--oneshot", "--quiet"):
            assert flag in command

    def test_passes_the_routed_model(self, policy_file):
        config = load_config(policy_file)
        command = build_command(route("implement it", config), "implement it")
        assert command[command.index("--model") + 1] == "cloud/vendor/big-model"

    def test_prompt_is_passed_as_an_argument_not_interpolated(self, policy_file):
        # argv, never a shell string: injection via task text must be impossible.
        config = load_config(policy_file)
        nasty = 'hello"; rm -rf / #'
        command = build_command(route("x", config), nasty)
        assert nasty in command
        assert command[command.index("--query") + 1] == nasty

    def test_skills_are_repeated_flags(self, policy_file):
        config = load_config(policy_file)
        command = build_command(route("x", config), "x", skills=["a", "b"])
        assert command.count("--skills") == 2

    def test_interactive_mode_omits_oneshot(self, policy_file):
        config = load_config(policy_file)
        command = build_command(route("x", config), "x", oneshot=False, quiet=False)
        assert "--oneshot" not in command and "--quiet" not in command


class TestSkillsBlock:
    """How the rendered config tells Hermes where the procedures live."""

    def test_points_hermes_at_the_library_in_place(self, policy_file, tmp_path, monkeypatch):
        root = tmp_path / "skills"
        root.mkdir()
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        skills = render_config(load_config(policy_file))["skills"]
        assert skills["enabled"] is True
        assert skills["external_dirs"] == [str(root.resolve())]

    def test_the_path_is_absolute(self, policy_file, monkeypatch, tmp_path):
        # The agent's working directory is not ours, and Hermes silently skips
        # an external dir that does not resolve.
        monkeypatch.setenv("PFA_SKILLS_DIR", "skills")
        [declared] = render_config(load_config(policy_file))["skills"]["external_dirs"]
        assert Path(declared).is_absolute()

    def test_the_rendered_file_carries_it(self, policy_file, tmp_path, monkeypatch):
        root = tmp_path / "skills"
        root.mkdir()
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        path = write_config(load_config(policy_file), home=tmp_path / "hermes")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert document["skills"]["external_dirs"] == [str(root.resolve())]
