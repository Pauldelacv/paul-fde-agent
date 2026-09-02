"""Executing a routed task through Hermes and recording what happened.

The runner is a thin, honest wrapper: it decides, it invokes, it records. It
does not parse or reinterpret the agent's answer — that output belongs to the
user, verbatim.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .errors import RuntimeMissingError
from .hermes import build_command, find_hermes
from .observability import RunRecord, write_record
from .router import Decision, route
from .skills import Library
from .skills import resolve as resolve_skills


@dataclass
class RunResult:
    decision: Decision
    record: RunRecord
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.record.status == "success"


def resolve_attached_skills(
    decision: Decision,
    requested: list[str] | None = None,
    library: Library | None = None,
) -> tuple[str, ...]:
    """Combine the policy's skills for this category with any asked for by hand.

    Policy order first, then the extras, duplicates dropped. Every name is
    checked against the library *before* the run starts: a mistyped ``--skill``
    should cost an error message, not a session that quietly proceeds without
    the procedure it was supposed to follow.
    """
    return resolve_skills([*decision.skills, *(requested or [])], library=library)


def run_task(
    text: str,
    config: Config,
    task: str | None = None,
    skills: list[str] | None = None,
    dry_run: bool = False,
    timeout: int | None = None,
    log_directory: Path | None = None,
    auto_skills: bool = True,
    library: Library | None = None,
) -> RunResult:
    """Route ``text``, run it through Hermes, and append a structured log record.

    With ``dry_run=True`` the routing decision is made and logged but no model is
    invoked — useful for validating a policy change without spending anything.
    Skill resolution still happens on that path, deliberately: a dry run that
    skipped it would not validate the thing most likely to be wrong.
    """
    decision = route(text, config, task=task, auto_skills=auto_skills)
    attached = resolve_attached_skills(decision, skills, library=library)
    record = RunRecord(
        task=decision.task,
        task_basis=decision.basis,
        provider=decision.provider.name,
        model=decision.model,
        skills=list(attached),
        dry_run=dry_run,
    )

    if dry_run:
        record.status = "success"
        record.exit_code = 0
        write_record(record, log_directory)
        return RunResult(decision=decision, record=record)

    executable = find_hermes()
    if not executable:
        record.status = "error"
        record.error = "hermes executable not found on PATH"
        write_record(record, log_directory)
        raise RuntimeMissingError(
            "The Hermes runtime is not installed.\n"
            "  Install it with:  pip install 'paul-fde-agent[hermes]'\n"
            "  Or run inside Docker:  make up\n"
            "  Then verify with:  pfa doctor"
        )

    command = build_command(decision, text, skills=list(attached), executable=executable)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired:
        record.duration_ms = int((time.monotonic() - started) * 1000)
        record.status = "error"
        record.error = f"hermes timed out after {timeout}s"
        write_record(record, log_directory)
        return RunResult(decision=decision, record=record, stderr=record.error)

    record.duration_ms = int((time.monotonic() - started) * 1000)
    record.exit_code = exit_code
    record.status = "success" if exit_code == 0 else "error"
    if exit_code != 0:
        # Keep the tail only: Hermes stderr can be long and we log it verbatim
        # (after redaction) into a file the operator may share.
        record.error = (stderr or "").strip()[-2000:] or f"exit code {exit_code}"

    write_record(record, log_directory)
    return RunResult(decision=decision, record=record, stdout=stdout, stderr=stderr)
