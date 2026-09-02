# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""CLI surface: exit codes, output shape, and the contract each command keeps."""

from __future__ import annotations

import json

import pytest
from conftest import write_skill

from pfa.cli import main


@pytest.fixture
def argv(policy_file):
    """Build an argv prefix pinned to the throwaway policy."""
    return lambda *rest: ["--config", str(policy_file), *rest]


class TestRoute:
    def test_prints_a_human_explanation(self, argv, capsys):
        assert main(argv("route", "implement the parser")) == 0
        assert "coding" in capsys.readouterr().out

    def test_json_output_is_machine_readable(self, argv, capsys):
        assert main(argv("route", "research this", "--json")) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["task"] == "research"
        assert payload["local"] is True

    def test_explicit_task_is_reported_as_explicit(self, argv, capsys):
        main(argv("route", "anything", "--task", "coding", "--json"))
        assert json.loads(capsys.readouterr().out)["basis"] == "explicit"

    def test_unknown_task_exits_with_an_error(self, argv, capsys):
        assert main(argv("route", "x", "--task", "bogus")) == 2
        assert "Unknown task category" in capsys.readouterr().err


class TestRun:
    def test_dry_run_succeeds_without_a_runtime(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path))
        assert main(argv("run", "research this", "--dry-run")) == 0
        assert "dry run" in capsys.readouterr().err

    def test_dry_run_json_emits_the_run_record(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path))
        main(argv("run", "research this", "--dry-run", "--json"))
        record = json.loads(capsys.readouterr().out)
        assert record["task"] == "research" and record["dry_run"] is True

    def test_missing_runtime_exits_two_with_guidance(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path))
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: None)
        assert main(argv("run", "research this")) == 2
        assert "pip install" in capsys.readouterr().err


class TestConfigCommand:
    def test_lists_providers_and_routes(self, argv, capsys):
        assert main(argv("config")) == 0
        out = capsys.readouterr().out
        assert "providers:" in out and "routes:" in out
        assert "coding" in out and "research" in out

    def test_never_prints_a_credential(self, argv, monkeypatch, capsys):
        monkeypatch.setenv("TEST_CLOUD_KEY", "sk-verysecretvalue1234567890")
        main(argv("config"))
        out = capsys.readouterr().out
        assert "sk-verysecretvalue1234567890" not in out
        assert "$TEST_CLOUD_KEY" in out, "it must show the variable NAME"


class TestDoctor:
    def test_json_output_lists_checks(self, argv, capsys):
        main(argv("doctor", "--json"))
        checks = json.loads(capsys.readouterr().out)
        assert any(c["name"] == "routing policy" for c in checks)
        assert all({"name", "status", "detail"} <= set(c) for c in checks)

    def test_reports_a_nonzero_exit_when_the_runtime_is_absent(self, argv, monkeypatch):
        monkeypatch.setattr("pfa.doctor.find_hermes", lambda: None)
        assert main(argv("doctor")) == 2

    def test_broken_policy_fails_rather_than_crashing(self, tmp_path, capsys):
        broken = tmp_path / "broken.yaml"
        broken.write_text("version: 99\n", encoding="utf-8")
        assert main(["--config", str(broken), "doctor"]) == 2
        assert "FAIL" in capsys.readouterr().out


class TestHermesConfigCommand:
    def test_prints_yaml_without_writing(self, argv, capsys):
        assert main(argv("hermes-config")) == 0
        assert "providers:" in capsys.readouterr().out

    def test_write_creates_the_file(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        assert main(argv("hermes-config", "--write")) == 0
        assert (tmp_path / "hermes" / "config.yaml").is_file()
        assert "Wrote" in capsys.readouterr().out

    def test_autonomy_choice_is_reflected(self, argv, capsys):
        main(argv("hermes-config", "--autonomy", "read"))
        assert "mode: manual" in capsys.readouterr().out


class TestAutonomyCommand:
    def test_describes_all_four_levels(self, argv, capsys):
        assert main(argv("autonomy")) == 0
        out = capsys.readouterr().out
        for level in ("READ", "PROPOSE", "EXECUTE", "EXTERNAL"):
            assert level in out


class TestLogsCommand:
    def test_reports_absence_gracefully(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path / "empty"))
        assert main(argv("logs")) == 0
        assert "No run logs" in capsys.readouterr().out

    def test_shows_a_previously_recorded_run(self, argv, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path))
        main(argv("run", "research this", "--dry-run"))
        capsys.readouterr()
        assert main(argv("logs")) == 0
        assert "research" in capsys.readouterr().out


class TestSkillsCommand:
    @pytest.fixture
    def argv_skills(self, policy_with_skills):
        """argv pinned to the policy that attaches the throwaway procedures."""
        return lambda *rest: ["--config", str(policy_with_skills), *rest]

    def test_bare_command_lists_the_library(self, argv_skills, skills_root, capsys):
        assert main(argv_skills("skills")) == 0
        out = capsys.readouterr().out
        assert "alpha-procedure" in out and "beta-procedure" in out

    def test_listing_says_where_each_skill_attaches(self, argv_skills, skills_root, capsys):
        main(argv_skills("skills", "list"))
        out = capsys.readouterr().out
        assert "attached to: research, coding" in out or "attached to: coding, research" in out

    def test_listing_marks_an_unattached_skill_as_explicit_only(
        self, argv_skills, skills_root, tmp_path, capsys
    ):
        write_skill(skills_root, "gamma-procedure")
        main(argv_skills("skills", "list"))
        out = capsys.readouterr().out
        assert "explicit only (--skill)" in out

    def test_json_listing_is_machine_readable(self, argv_skills, skills_root, capsys):
        assert main(argv_skills("skills", "list", "--json")) == 0
        payload = json.loads(capsys.readouterr().out)
        names = {entry["name"] for entry in payload}
        assert {"alpha-procedure", "beta-procedure"} == names
        alpha = next(e for e in payload if e["name"] == "alpha-procedure")
        assert sorted(alpha["attached_to"]) == ["coding", "research"]

    def test_empty_library_says_where_it_looked(self, argv_skills, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "nowhere"))
        assert main(argv_skills("skills")) == 0
        assert "No skills found" in capsys.readouterr().out

    def test_show_prints_the_whole_file(self, argv_skills, skills_root, capsys):
        assert main(argv_skills("skills", "show", "alpha-procedure")) == 0
        out = capsys.readouterr().out
        assert out.startswith("---") and "# Procedure" in out

    def test_show_rejects_an_unknown_name_and_lists_the_real_ones(
        self, argv_skills, skills_root, capsys
    ):
        assert main(argv_skills("skills", "show", "nope")) == 2
        assert "Available: alpha-procedure" in capsys.readouterr().err

    def test_validate_passes_on_a_clean_library(self, argv_skills, skills_root, capsys):
        assert main(argv_skills("skills", "validate")) == 0
        assert "Validated 2 skills" in capsys.readouterr().out

    def test_validate_exits_nonzero_and_names_the_broken_file(
        self, argv_skills, skills_root, capsys
    ):
        broken = skills_root / "fde" / "broken-procedure"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter\n", encoding="utf-8")
        assert main(argv_skills("skills", "validate")) == 1
        assert "broken-procedure" in capsys.readouterr().err

    def test_install_writes_into_the_hermes_tree(
        self, argv_skills, skills_root, tmp_path, monkeypatch, capsys
    ):
        home = tmp_path / "hermes"
        monkeypatch.setenv("HERMES_HOME", str(home))
        assert main(argv_skills("skills", "install")) == 0
        assert (home / "skills" / "fde" / "alpha-procedure" / "SKILL.md").is_file()
        assert "Installed 2 skills" in capsys.readouterr().out

    def test_install_honours_an_explicit_home(self, argv_skills, skills_root, tmp_path, capsys):
        home = tmp_path / "elsewhere"
        assert main(argv_skills("skills", "install", "--home", str(home))) == 0
        assert (home / "skills" / "fde" / "beta-procedure" / "SKILL.md").is_file()

    def test_listing_survives_an_unloadable_policy(self, tmp_path, skills_root, capsys):
        # `pfa skills` must keep working when the thing being debugged is the policy.
        broken = tmp_path / "broken.yaml"
        broken.write_text("version: 99\n", encoding="utf-8")
        assert main(["--config", str(broken), "skills"]) == 0
        assert "alpha-procedure" in capsys.readouterr().out


class TestSkillsInRouteAndRun:
    @pytest.fixture
    def argv_skills(self, policy_with_skills):
        return lambda *rest: ["--config", str(policy_with_skills), *rest]

    def test_route_reports_the_attached_procedures(self, argv_skills, capsys):
        assert main(argv_skills("route", "research this")) == 0
        assert "skills: alpha-procedure" in capsys.readouterr().out

    def test_route_json_carries_them(self, argv_skills, capsys):
        main(argv_skills("route", "research this", "--json"))
        assert json.loads(capsys.readouterr().out)["skills"] == ["alpha-procedure"]

    def test_route_no_auto_skills_suppresses_them(self, argv_skills, capsys):
        main(argv_skills("route", "research this", "--no-auto-skills", "--json"))
        payload = json.loads(capsys.readouterr().out)
        assert payload["skills"] == [] and payload["task"] == "research"

    def test_dry_run_records_the_attached_procedures(
        self, argv_skills, skills_root, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path / "logs"))
        main(argv_skills("run", "research this", "--dry-run", "--json"))
        assert json.loads(capsys.readouterr().out)["skills"] == ["alpha-procedure"]

    def test_a_mistyped_skill_exits_two_with_the_available_names(
        self, argv_skills, skills_root, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("PFA_LOG_DIR", str(tmp_path / "logs"))
        assert main(argv_skills("run", "research this", "--skill", "typo", "--dry-run")) == 2
        assert "Available: alpha-procedure" in capsys.readouterr().err

    def test_config_command_shows_the_attachments(self, argv_skills, capsys):
        assert main(argv_skills("config")) == 0
        out = capsys.readouterr().out
        assert "skills: alpha-procedure" in out and "skill library:" in out


class TestParser:
    def test_requires_a_subcommand(self):
        with pytest.raises(SystemExit):
            main([])

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert "pfa" in capsys.readouterr().out
