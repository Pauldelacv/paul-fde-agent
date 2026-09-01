"""Runner behaviour, with the Hermes subprocess stubbed out.

No test here launches a model. `run_task` is exercised by patching the two
seams it depends on: locating the executable, and `subprocess.run`.
"""

from __future__ import annotations

import subprocess

import pytest

from pfa.config import load_config
from pfa.errors import RuntimeMissingError
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
