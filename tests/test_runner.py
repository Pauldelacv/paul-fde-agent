"""Runner behaviour, with the Hermes subprocess stubbed out.

No test here launches a model. `run_task` is exercised by patching the two
seams it depends on: locating the executable, and `subprocess.run`.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from pfa.config import load_config
from pfa.errors import RuntimeMissingError, SkillError
from pfa.runner import run_task


@pytest.fixture
def config(policy_file):
    return load_config(policy_file)


class FakeCompleted:
    def __init__(self, returncode=0, stdout="answer", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestDryRun:
    def test_invokes_nothing(self, config, tmp_path, monkeypatch):
        def explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("dry run must not spawn a process")

        monkeypatch.setattr(subprocess, "run", explode)
        result = run_task("research this", config, dry_run=True, log_directory=tmp_path)
        assert result.ok and result.record.dry_run is True

    def test_still_records_the_decision(self, config, tmp_path):
        result = run_task("implement this", config, dry_run=True, log_directory=tmp_path)
        assert result.record.task == "coding"
        assert result.record.provider == "cloud"


class TestExecution:
    def test_returns_stdout_on_success(self, config, tmp_path, monkeypatch):
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted(0, "the answer"))
        result = run_task("research this", config, log_directory=tmp_path)
        assert result.ok and result.stdout == "the answer"

    def test_marks_failure_and_captures_stderr(self, config, tmp_path, monkeypatch):
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted(3, "", "boom"))
        result = run_task("research this", config, log_directory=tmp_path)
        assert not result.ok
        assert result.record.exit_code == 3
        assert "boom" in result.record.error

    def test_passes_the_routed_model_to_the_subprocess(self, config, tmp_path, monkeypatch):
        captured = {}

        def capture(command, **kwargs):
            captured["command"] = command
            return FakeCompleted()

        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", capture)
        run_task("implement this", config, log_directory=tmp_path)
        command = captured["command"]
        assert command[command.index("--model") + 1] == "cloud/vendor/big-model"

    def test_timeout_is_recorded_not_raised(self, config, tmp_path, monkeypatch):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="hermes", timeout=1)

        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", timeout)
        result = run_task("research this", config, timeout=1, log_directory=tmp_path)
        assert result.record.status == "error"
        assert "timed out" in result.record.error


class TestMissingRuntime:
    def test_raises_actionable_error(self, config, tmp_path, monkeypatch):
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: None)
        with pytest.raises(RuntimeMissingError) as excinfo:
            run_task("research this", config, log_directory=tmp_path)
        message = str(excinfo.value)
        assert "pip install" in message and "pfa doctor" in message

    def test_failure_is_logged_before_raising(self, config, tmp_path, monkeypatch):
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: None)
        with pytest.raises(RuntimeMissingError):
            run_task("research this", config, log_directory=tmp_path)
        assert list(tmp_path.glob("runs-*.jsonl")), "the failed run must still be recorded"


class TestSkillAttachment:
    """What the runner hands Hermes, and what it refuses to hand it."""

    @pytest.fixture
    def config_with_skills(self, policy_with_skills):
        return load_config(policy_with_skills)

    def test_policy_skills_reach_the_command(
        self, config_with_skills, skills_root, tmp_path, monkeypatch
    ):
        captured = {}

        def capture(command, **kwargs):
            captured["command"] = command
            return FakeCompleted()

        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", capture)
        run_task("research this", config_with_skills, log_directory=tmp_path)

        command = captured["command"]
        assert command.count("--skills") == 1
        assert command[command.index("--skills") + 1] == "alpha-procedure"

    def test_explicit_skills_are_appended_after_the_policy_ones(
        self, config_with_skills, skills_root, tmp_path, monkeypatch
    ):
        captured = {}
        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda command, **kwargs: (captured.update(command=command), FakeCompleted())[1],
        )
        run_task(
            "research this",
            config_with_skills,
            skills=["beta-procedure"],
            log_directory=tmp_path,
        )
        command = captured["command"]
        names = [command[i + 1] for i, arg in enumerate(command) if arg == "--skills"]
        assert names == ["alpha-procedure", "beta-procedure"]

    def test_a_skill_requested_twice_is_passed_once(
        self, config_with_skills, skills_root, tmp_path
    ):
        result = run_task(
            "research this",
            config_with_skills,
            skills=["alpha-procedure"],
            dry_run=True,
            log_directory=tmp_path,
        )
        assert result.record.skills == ["alpha-procedure"]

    def test_no_auto_skills_leaves_only_what_was_asked_for(
        self, config_with_skills, skills_root, tmp_path
    ):
        result = run_task(
            "research this",
            config_with_skills,
            skills=["beta-procedure"],
            auto_skills=False,
            dry_run=True,
            log_directory=tmp_path,
        )
        assert result.record.skills == ["beta-procedure"]

    def test_the_attached_skills_are_recorded_in_the_log(
        self, config_with_skills, skills_root, tmp_path
    ):
        run_task("research this", config_with_skills, dry_run=True, log_directory=tmp_path)
        line = next(tmp_path.glob("runs-*.jsonl")).read_text(encoding="utf-8").strip()
        assert json.loads(line)["skills"] == ["alpha-procedure"]

    def test_an_unknown_skill_fails_before_anything_is_spent(
        self, config_with_skills, skills_root, tmp_path, monkeypatch
    ):
        def explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("a mistyped skill must not reach the runtime")

        monkeypatch.setattr("pfa.runner.find_hermes", lambda: "/usr/bin/hermes")
        monkeypatch.setattr(subprocess, "run", explode)
        with pytest.raises(SkillError, match="Unknown skill 'typo'"):
            run_task("research this", config_with_skills, skills=["typo"], log_directory=tmp_path)

    def test_a_dry_run_validates_skills_too(self, config_with_skills, skills_root, tmp_path):
        # A dry run whose whole point is validating a policy change would be
        # worthless if it skipped the part most likely to be wrong.
        with pytest.raises(SkillError):
            run_task(
                "research this",
                config_with_skills,
                skills=["typo"],
                dry_run=True,
                log_directory=tmp_path,
            )

    def test_a_policy_naming_a_missing_skill_is_reported(
        self, config_with_skills, tmp_path, monkeypatch
    ):
        # No skills_root fixture here: the library is empty, so the policy's
        # own reference cannot resolve.
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "no-skills-here"))
        with pytest.raises(SkillError, match="alpha-procedure"):
            run_task("research this", config_with_skills, dry_run=True, log_directory=tmp_path)

    def test_a_skill_free_route_needs_no_library_at_all(
        self, config_with_skills, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "no-skills-here"))
        result = run_task(
            "something ordinary", config_with_skills, dry_run=True, log_directory=tmp_path
        )
        assert result.ok and result.record.skills == []
