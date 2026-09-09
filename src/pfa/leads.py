"""The lead-generation vertical: prospect lists, suppression, and drafting.

What this module is for
-----------------------
The rest of this project routes a free-form task to a model. Prospecting needs
something the router cannot supply: a list of real people, held somewhere that
is not the repository, checked against the people who have asked not to be
contacted, and turned into one draft per prospect that a human then reviews.

Three properties are structural rather than conventional, and the tests assert
all three:

**Nothing is ever sent.** :func:`draft_for` produces a file. There is no send
path in this module, no transport, and no credential for one. Sending is a
human action taken in the sending tool after reading the draft. This is what
makes an agent with a mailbox-shaped job safe to run unattended, and it is the
same reason the lemlist connector excludes the send tools.

**Personal data never enters the repository.** Everything lives under
``$PFA_PRIVATE_DIR`` (``private/`` by default), which is gitignored, and a
security test asserts it stays untracked. The routing policy sends this
category to the local model for the matching reason: a prospect list that never
leaves the machine has no international transfer to document.

**Suppression is checked before anything else happens.** Not at send time —
there is no send time — but before enrichment, before drafting, before a
prospect is shown. An objection is permanent, and the check that enforces it
has to sit earlier than the step someone might skip.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from .config import Config
from .errors import PfaError
from .runner import RunResult, run_task

DEFAULT_PRIVATE_DIR = Path("private")

PROSPECTS_FILE = "prospects.csv"
SUPPRESSION_FILE = "suppression.txt"
DRAFTS_DIR = "drafts"

#: The columns a prospect row carries. `source` and `collected_at` are not
#: bookkeeping: Article 14 requires telling someone where their data came from,
#: so a row without them describes a person who cannot lawfully be contacted.
COLUMNS = (
    "email",
    "first_name",
    "last_name",
    "role",
    "company",
    "source",
    "collected_at",
    "trigger",
    "trigger_source",
    "notes",
)

#: Deliberately permissive. This is a shape check to catch a mangled CSV cell,
#: not an attempt to decide deliverability — that is what verification is for,
#: and a regular expression has never established that an address exists.
_EMAIL = re.compile(r"\A[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}\Z")

_ISO_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


class LeadsError(PfaError):
    """The prospect list, or the directory holding it, is missing or malformed."""


def private_dir() -> Path:
    """Where operational personal data lives: ``$PFA_PRIVATE_DIR``, else ``private/``."""
    return Path(os.environ.get("PFA_PRIVATE_DIR") or DEFAULT_PRIVATE_DIR)


def normalise_email(value: str) -> str:
    """Lowercase and strip, and nothing more.

    Not stripping ``+tags`` or dots is deliberate. Those rules differ per
    provider, and a wrong guess on the suppression path means contacting
    someone who asked not to be — the one error this module must not make.
    """
    return value.strip().lower()


@dataclass(frozen=True)
class Prospect:
    """One person on the list, and the provenance that makes contacting them lawful."""

    email: str
    first_name: str = ""
    last_name: str = ""
    role: str = ""
    company: str = ""
    source: str = ""
    collected_at: str = ""
    trigger: str = ""
    trigger_source: str = ""
    notes: str = ""
    row: int = 0

    @property
    def name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part).strip()

    @property
    def label(self) -> str:
        """How this prospect is named in output. Never a bare address alone."""
        who = self.name or self.email
        return f"{who} ({self.company})" if self.company else who

    @property
    def slug(self) -> str:
        """A filesystem-safe identifier for the draft file."""
        base = re.sub(r"[^a-z0-9]+", "-", normalise_email(self.email)).strip("-")
        return base or f"row-{self.row}"

    def blockers(self) -> tuple[str, ...]:
        """Reasons this prospect may not be drafted for, in the order they matter.

        A blocker is a compliance or data problem, not a quality one: a prospect
        with no trigger produces a weak message, but a prospect with no recorded
        source cannot be given the Article 14 notice at all.
        """
        problems: list[str] = []
        if not self.email:
            problems.append("no email address")
        elif not _EMAIL.match(self.email):
            problems.append(f"email {self.email!r} is not a plausible address")
        if not self.source:
            problems.append("no `source` — Article 14 requires telling them where data came from")
        if not self.collected_at:
            problems.append("no `collected_at` — retention cannot be enforced without it")
        elif not _ISO_DATE.match(self.collected_at):
            problems.append(f"collected_at {self.collected_at!r} is not YYYY-MM-DD")
        return tuple(problems)

    def warnings(self) -> tuple[str, ...]:
        """Quality problems: a draft is possible, but it will be a poor one."""
        problems: list[str] = []
        if not self.trigger:
            problems.append("no `trigger` — there is no stated reason to write now")
        elif not self.trigger_source:
            problems.append("`trigger` has no `trigger_source` — the claim is unverifiable")
        if not self.name:
            problems.append("no name — the message cannot address anyone")
        return tuple(problems)


@dataclass
class Suppression:
    """Addresses that must never be contacted again.

    Kept as a plain text file, one address per line, because it has to survive
    everything else: a database migration, a tool change, a restore from backup.
    Comments and blank lines are ignored so a reason can be written beside an
    entry without a schema.
    """

    path: Path
    entries: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> Suppression:
        """Read the list. A missing file is an empty list, never an error.

        The alternative — refusing to run without one — would push an operator
        toward creating an empty file to get past the error, which is the same
        state with less information.
        """
        entries: set[str] = set()
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.split("#", 1)[0].strip()
                if text:
                    entries.add(normalise_email(text))
        return cls(path=path, entries=entries)

    def contains(self, email: str) -> bool:
        return normalise_email(email) in self.entries

    def add(self, email: str, reason: str = "") -> bool:
        """Append an address. Returns False if it was already suppressed.

        Appends rather than rewrites: this file is the one record that must not
        lose an entry to a partial write.
        """
        normalised = normalise_email(email)
        if not normalised:
            raise LeadsError("Cannot suppress an empty address.")
        if normalised in self.entries:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).date().isoformat()
        comment = f"  # {stamp}{' ' + reason if reason else ''}"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{normalised}{comment}\n")
        self.entries.add(normalised)
        return True


def load_prospects(path: Path | None = None) -> tuple[Prospect, ...]:
    """Read the prospect list from CSV.

    Raises :class:`LeadsError` with the command that fixes it when the file is
    absent or has the wrong header — both of which are setup mistakes an
    operator should be told how to correct, not stack traces.
    """
    target = path or (private_dir() / PROSPECTS_FILE)
    if not target.is_file():
        raise LeadsError(
            f"No prospect list at {target}. Create one with `pfa leads init`, "
            f"or set PFA_PRIVATE_DIR to where yours lives."
        )

    # Comment lines are stripped before parsing so the file can carry the
    # warning at the top of it — a CSV of personal data should say what it is
    # when someone opens it, and DictReader would otherwise take that banner
    # for the header row. Their original line numbers are kept alongside, so
    # an error still points at the line the operator has to go and edit.
    numbered = [
        (number, line)
        for number, line in enumerate(
            target.read_text(encoding="utf-8").splitlines(keepends=True), start=1
        )
        if not line.lstrip().startswith("#")
    ]

    reader = csv.DictReader([line for _, line in numbered])
    header = reader.fieldnames or []
    missing = [column for column in ("email", "source", "collected_at") if column not in header]
    if missing:
        raise LeadsError(
            f"{target} is missing required column(s): {', '.join(missing)}. "
            f"Expected header: {','.join(COLUMNS)}"
        )

    data_lines = [number for number, _ in numbered[1:]]  # the header is consumed first
    prospects = []
    for index, row in enumerate(reader):
        values = {key: (row.get(key) or "").strip() for key in COLUMNS}
        if not any(values.values()):
            continue
        values["email"] = normalise_email(values["email"])
        line_number = data_lines[index] if index < len(data_lines) else 0
        prospects.append(Prospect(**values, row=line_number))
    return tuple(prospects)


@dataclass(frozen=True)
class PreflightEntry:
    prospect: Prospect
    suppressed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def draftable(self) -> bool:
        return not self.suppressed and not self.blockers

    @property
    def state(self) -> str:
        if self.suppressed:
            return "suppressed"
        if self.blockers:
            return "blocked"
        if self.warnings:
            return "weak"
        return "ready"


@dataclass(frozen=True)
class Preflight:
    """The whole list, judged. What `pfa leads check` prints and `draft` obeys."""

    entries: tuple[PreflightEntry, ...]
    suppression: Suppression
    duplicates: tuple[str, ...] = ()

    @property
    def draftable(self) -> tuple[PreflightEntry, ...]:
        return tuple(entry for entry in self.entries if entry.draftable)

    def counts(self) -> dict[str, int]:
        counts = {"ready": 0, "weak": 0, "blocked": 0, "suppressed": 0}
        for entry in self.entries:
            counts[entry.state] += 1
        return counts


def preflight(
    prospects: tuple[Prospect, ...] | list[Prospect],
    suppression: Suppression,
) -> Preflight:
    """Check every prospect against the suppression list and the record-keeping rules.

    Suppression is evaluated first for each prospect and short-circuits the
    rest: someone who has objected is not a data-quality problem to be fixed.
    """
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    entries: list[PreflightEntry] = []
    for prospect in prospects:
        if prospect.email:
            if prospect.email in seen:
                duplicates.append(prospect.email)
            else:
                seen[prospect.email] = prospect.row
        suppressed = bool(prospect.email) and suppression.contains(prospect.email)
        entries.append(
            PreflightEntry(
                prospect=prospect,
                suppressed=suppressed,
                blockers=() if suppressed else prospect.blockers(),
                warnings=() if suppressed else prospect.warnings(),
            )
        )
    return Preflight(
        entries=tuple(entries),
        suppression=suppression,
        duplicates=tuple(dict.fromkeys(duplicates)),
    )


def draft_prompt(prospect: Prospect) -> str:
    """The task text handed to the agent for one prospect.

    Everything the procedures need is stated here rather than assumed, including
    the instruction not to send — the model has no send tool, but a prompt that
    implies sending produces a draft written as though it were already gone.
    """
    known = [
        f"- Name: {prospect.name or '(unknown)'}",
        f"- Role: {prospect.role or '(unknown)'}",
        f"- Company: {prospect.company or '(unknown)'}",
        f"- Email: {prospect.email}",
        f"- Where this contact came from: {prospect.source}",
        f"- Recorded on: {prospect.collected_at}",
    ]
    if prospect.trigger:
        source = prospect.trigger_source or "NO SOURCE RECORDED"
        known.append(f"- Trigger observed: {prospect.trigger} (source: {source})")
    if prospect.notes:
        known.append(f"- Notes: {prospect.notes}")

    return (
        "Write one cold outreach email to this prospect, following the "
        "outreach-writing procedure.\n\n"
        "What is known about them — use nothing beyond this, and do not invent "
        "anything to fill a gap:\n" + "\n".join(known) + "\n\n"
        "Requirements:\n"
        "- Under 120 words in the body, one ask, answerable in a word.\n"
        "- Every personalised claim must trace to the trigger above. If no "
        "trigger is recorded, say so plainly and write the most honest "
        "non-personalised message you can, rather than inventing an observation.\n"
        "- Include the Article 14 notice and an opt-out placeholder, naming the "
        "source above as where their data came from.\n"
        "- Output the draft in the outreach-writing Output Template, including "
        "the claims-and-sources table.\n\n"
        "This is a draft for human review. It will not be sent by you."
    )


def draft_path(prospect: Prospect, root: Path | None = None, on: date | None = None) -> Path:
    """Where one prospect's draft is written: ``drafts/<date>/<slug>.md``."""
    base = root or (private_dir() / DRAFTS_DIR)
    day = (on or datetime.now(UTC).date()).isoformat()
    return base / day / f"{prospect.slug}.md"


def draft_for(
    prospect: Prospect,
    config: Config,
    *,
    suppression: Suppression,
    drafts_root: Path | None = None,
    timeout: int | None = None,
) -> tuple[Path, RunResult]:
    """Run the agent for one prospect and write the draft. Never sends anything.

    Re-checks suppression here rather than trusting the caller's preflight. The
    two checks look redundant and are not: this function is importable, and the
    guarantee it makes has to hold for a caller that skipped the preflight.
    """
    if suppression.contains(prospect.email):
        raise LeadsError(
            f"{prospect.email} is on the suppression list ({suppression.path}). "
            f"They asked not to be contacted; that decision is permanent."
        )
    blockers = prospect.blockers()
    if blockers:
        raise LeadsError(
            f"Cannot draft for row {prospect.row} ({prospect.email or 'no address'}): "
            + "; ".join(blockers)
        )

    result = run_task(
        draft_prompt(prospect),
        config,
        task="prospecting",
        skills=["outreach-writing"],
        timeout=timeout,
    )

    path = draft_path(prospect, drafts_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = result.stdout.strip() or "(the model returned nothing)"
    path.write_text(
        f"# Draft — {prospect.label}\n\n"
        f"- Prospect: {prospect.email}\n"
        f"- Source of the contact: {prospect.source} (recorded {prospect.collected_at})\n"
        f"- Trigger: {prospect.trigger or '(none recorded)'}"
        f"{f' — source: {prospect.trigger_source}' if prospect.trigger_source else ''}\n"
        f"- Generated: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"- Model: {result.decision.model_ref}\n"
        f"- Status: **awaiting human review. Not sent.**\n\n"
        f"---\n\n{body}\n",
        encoding="utf-8",
    )
    return path, result


TEMPLATE_HEADER = """# Prospect list — PERSONAL DATA. Never commit this file.
# One person per row. `source` and `collected_at` are required: Article 14
# obliges you to tell someone where their data came from, and retention cannot
# be enforced without a date. `trigger` is what makes the message worth sending;
# `trigger_source` is what makes the claim checkable.
"""


def init_private_dir(root: Path | None = None) -> tuple[Path, Path]:
    """Create the prospect list and suppression file from templates.

    Refuses to overwrite either. The prospect list is hand-maintained personal
    data and the suppression list is the one file whose loss re-contacts people
    who objected; neither is something a convenience flag should be able to
    clobber.
    """
    base = root or private_dir()
    base.mkdir(parents=True, exist_ok=True)
    prospects = base / PROSPECTS_FILE
    suppression = base / SUPPRESSION_FILE

    existing = [path for path in (prospects, suppression) if path.exists()]
    if existing:
        raise LeadsError(
            f"Refusing to overwrite existing file(s): {', '.join(str(p) for p in existing)}. "
            f"Delete them by hand if you really mean to start over."
        )

    today = datetime.now(UTC).date().isoformat()
    with prospects.open("w", newline="", encoding="utf-8") as handle:
        handle.write(TEMPLATE_HEADER)
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerow(
            [
                "ada.lovelace@example.com",
                "Ada",
                "Lovelace",
                "CTO",
                "Example Analytical Ltd",
                "conference attendee list, published by the organiser",
                today,
                "posted a role mentioning GDPR-compliant data processing",
                "their careers page",
                "replace this row with real prospects",
            ]
        )

    suppression.write_text(
        "# Addresses that must never be contacted again. One per line.\n"
        "# An objection is permanent: nothing is ever removed from this file.\n"
        "# Checked before enrichment, before drafting, before anything.\n",
        encoding="utf-8",
    )
    return prospects, suppression
