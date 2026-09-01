# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""CLI surface: exit codes, output shape, and the contract each command keeps."""

from __future__ import annotations

import json

import pytest

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


class TestParser:
    def test_requires_a_subcommand(self):
        with pytest.raises(SystemExit):
            main([])

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert "pfa" in capsys.readouterr().out
