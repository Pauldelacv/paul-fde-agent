"""The FDE skill library: discovery, validation and installation.

A skill is a procedure in `agentskills.io <https://agentskills.io>`_ format —
YAML frontmatter followed by Markdown — living at
``skills/<category>/<name>/SKILL.md``. That layout is not an invention of this
project: it is the one Hermes reads from ``$HERMES_HOME/skills``, so a procedure
written here is portable to any Hermes installation without translation.

This module exists because Phase 2 took the library from one skill to five, and
five is the point at which three questions stop having obvious answers:

  1. *which skills exist* — ``pfa skills``,
  2. *are they well-formed* — ``pfa skills validate`` and ``pfa doctor``,
  3. *are they the ones Hermes will actually load* — ``pfa skills install``.

Question 3 is the one that bites. The repository is the source of truth; Hermes
reads a different directory. Nothing reconciled the two before Phase 2, so a
skill could be edited here and never reach the agent — a silent failure of
exactly the kind this project is meant not to have.

Validation never raises for a malformed skill on the *library* path: a broken
skill is reported as a problem alongside the ones that loaded, because an
operator needs to see the four that work and the one that does not, not a
traceback about the first file in alphabetical order.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import SkillError

DEFAULT_SKILLS_DIR = Path("skills")
SKILL_FILE = "SKILL.md"

#: A document opening with a `---` fenced YAML block, then the body.
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)

#: Directory and skill names: lowercase, digits, hyphens. The name becomes a
#: CLI argument and a path segment, so anything else is a future bug.
_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")

#: MAJOR.MINOR.PATCH. Not full semver — no pre-release or build metadata —
#: because a skill that needs a build identifier has a bigger problem.
_VERSION = re.compile(r"\A\d+\.\d+\.\d+\Z")

REQUIRED_FRONTMATTER = ("name", "description", "version")


@dataclass(frozen=True)
class Skill:
    """One validated procedure in the library."""

    name: str
    category: str
    description: str
    version: str
    path: Path
    tags: tuple[str, ...] = ()

    @property
    def reference(self) -> str:
        """``category/name`` — how the skill is addressed inside Hermes' tree."""
        return f"{self.category}/{self.name}"

    @property
    def directory(self) -> Path:
        return self.path.parent

    def body(self) -> str:
        """The Markdown below the frontmatter."""
        return split_frontmatter(self.path.read_text(encoding="utf-8"))[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "version": self.version,
            "tags": list(self.tags),
            "path": str(self.path),
        }


@dataclass(frozen=True)
class SkillProblem:
    """A skill that did not load, and what to do about it."""

    path: Path
    message: str
    remedy: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"path": str(self.path), "message": self.message, "remedy": self.remedy}


@dataclass(frozen=True)
class Library:
    """The result of scanning a skills directory: what loaded, and what did not."""

    root: Path
    skills: tuple[Skill, ...] = ()
    problems: tuple[SkillProblem, ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(skill.name for skill in self.skills)

    def get(self, name: str) -> Skill | None:
        return next((skill for skill in self.skills if skill.name == name), None)

    def require(self, name: str) -> Skill:
        """Look a skill up by name, or explain what is available instead."""
        found = self.get(name)
        if found is not None:
            return found
        if self.names:
            known = ", ".join(self.names)
            raise SkillError(f"Unknown skill {name!r}. Available: {known}.")
        raise SkillError(
            f"Unknown skill {name!r}; no skills loaded from {self.root}. "
            f"Run from the repository root or set PFA_SKILLS_DIR."
        )


# --- locating and reading --------------------------------------------------


def skills_dir() -> Path:
    """Where the library lives: ``$PFA_SKILLS_DIR``, else ``skills/``."""
    return Path(os.environ.get("PFA_SKILLS_DIR") or DEFAULT_SKILLS_DIR)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split an agentskills.io document into (frontmatter, body).

    Raises :class:`SkillError` when the fence is missing or the YAML inside it
    is not a mapping — both of which mean Hermes will not load the file either.
    """
    match = _FRONTMATTER.match(text.lstrip("﻿"))
    if not match:
        raise SkillError(
            "missing YAML frontmatter; the file must begin with a `---` fence, "
            "the metadata, and a closing `---`"
        )
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise SkillError(f"frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SkillError("frontmatter must be a mapping of keys to values")
    return parsed, match.group(2)


def load_skill(path: Path, category: str | None = None) -> Skill:
    """Read and validate one ``SKILL.md``.

    ``category`` defaults to the name of the grandparent directory, which is
    how Hermes derives it from ``skills/<category>/<name>/SKILL.md``.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillError(f"cannot be read: {exc}") from exc

    frontmatter, body = split_frontmatter(text)

    missing = [key for key in REQUIRED_FRONTMATTER if not str(frontmatter.get(key, "")).strip()]
    if missing:
        raise SkillError(f"frontmatter is missing required key(s): {', '.join(missing)}")

    name = str(frontmatter["name"]).strip()
    directory = path.parent.name
    if name != directory:
        raise SkillError(
            f"frontmatter name {name!r} does not match its directory {directory!r}; "
            f"the two are how the skill is addressed and must agree"
        )
    if not _NAME.match(name):
        raise SkillError(f"name {name!r} must be lowercase words joined by hyphens")

    version = str(frontmatter["version"]).strip()
    if not _VERSION.match(version):
        raise SkillError(f"version {version!r} must be MAJOR.MINOR.PATCH")

    if not body.strip():
        raise SkillError("has frontmatter but no body; a skill with no procedure teaches nothing")

    metadata = frontmatter.get("metadata")
    hermes = metadata.get("hermes") if isinstance(metadata, dict) else None
    raw_tags = hermes.get("tags") if isinstance(hermes, dict) else None
    tags = tuple(str(tag) for tag in raw_tags) if isinstance(raw_tags, list) else ()

    resolved_category = category or path.parent.parent.name
    if isinstance(hermes, dict) and hermes.get("category"):
        declared = str(hermes["category"]).strip()
        if declared != resolved_category:
            raise SkillError(
                f"metadata.hermes.category is {declared!r} but the skill sits under "
                f"{resolved_category!r}; move the directory or correct the frontmatter"
            )

    return Skill(
        name=name,
        category=resolved_category,
        description=str(frontmatter["description"]).strip(),
        version=version,
        path=path,
        tags=tags,
    )


def discover(root: Path | None = None) -> Library:
    """Scan ``root`` for ``*/*/SKILL.md`` and load every one it finds.

    Never raises. A malformed skill becomes a :class:`SkillProblem` so the
    operator sees the whole library state at once, not the first failure.
    """
    base = Path(root) if root is not None else skills_dir()
    if not base.is_dir():
        return Library(root=base)

    skills: list[Skill] = []
    problems: list[SkillProblem] = []
    seen: dict[str, Path] = {}

    for path in sorted(base.glob(f"*/*/{SKILL_FILE}")):
        try:
            skill = load_skill(path)
        except SkillError as exc:
            problems.append(
                SkillProblem(path=path, message=str(exc), remedy="Correct the file, then re-run.")
            )
            continue
        if skill.name in seen:
            problems.append(
                SkillProblem(
                    path=path,
                    message=(
                        f"duplicate skill name {skill.name!r}, "
                        f"already defined by {seen[skill.name]}"
                    ),
                    remedy="Rename one of the two; a name must address exactly one procedure.",
                )
            )
            continue
        seen[skill.name] = path
        skills.append(skill)

    # A directory that looks like a skill but has no SKILL.md is a mistake worth
    # reporting: it is invisible to Hermes and easy to miss in review.
    for candidate in sorted(base.glob("*/*")):
        if candidate.is_dir() and not (candidate / SKILL_FILE).is_file():
            problems.append(
                SkillProblem(
                    path=candidate,
                    message=f"directory contains no {SKILL_FILE}",
                    remedy=f"Add {candidate / SKILL_FILE}, or remove the directory.",
                )
            )

    skills.sort(key=lambda skill: (skill.category, skill.name))
    return Library(root=base, skills=tuple(skills), problems=tuple(problems))


# --- installation into the Hermes tree -------------------------------------


def hermes_skills_dir(home: Path) -> Path:
    return Path(home) / "skills"


def install_state(library: Library, home: Path) -> tuple[list[Skill], list[Skill], list[Skill]]:
    """Compare the library against ``$HERMES_HOME/skills``.

    Returns ``(installed, missing, stale)``. "Stale" means present but with
    different content — the case that silently runs an old procedure.
    """
    target_root = hermes_skills_dir(home)
    installed: list[Skill] = []
    missing: list[Skill] = []
    stale: list[Skill] = []

    for skill in library.skills:
        target = target_root / skill.category / skill.name / SKILL_FILE
        if not target.is_file():
            missing.append(skill)
            continue
        try:
            same = target.read_text(encoding="utf-8") == skill.path.read_text(encoding="utf-8")
        except OSError:
            same = False
        (installed if same else stale).append(skill)
    return installed, missing, stale


def install(library: Library, home: Path) -> list[Path]:
    """Copy every valid skill into ``$HERMES_HOME/skills``. Returns what was written.

    The repository is the source of truth, so existing files are overwritten.
    Invalid skills are skipped rather than half-copied: installing a procedure
    Hermes cannot parse would trade a visible error for an invisible one.
    """
    if not library.skills:
        raise SkillError(
            f"No valid skills to install from {library.root}. Run `pfa skills validate` to see why."
        )

    target_root = hermes_skills_dir(home)
    written: list[Path] = []
    for skill in library.skills:
        destination = target_root / skill.category / skill.name
        destination.mkdir(parents=True, exist_ok=True)
        # copytree, not copy(SKILL.md): a skill may ship reference files beside
        # its procedure, and they have to travel with it.
        shutil.copytree(skill.directory, destination, dirs_exist_ok=True)
        written.append(destination / SKILL_FILE)
    return written


# --- resolving what a run should load --------------------------------------


def resolve(
    requested: list[str] | tuple[str, ...],
    library: Library | None = None,
) -> tuple[str, ...]:
    """Validate requested skill names, preserving order and dropping duplicates.

    Called before Hermes is launched so a typo costs an error message rather
    than a session that quietly runs without the procedure it was supposed to
    follow.
    """
    if not requested:
        return ()
    resolved = library if library is not None else discover()
    ordered: list[str] = []
    for name in requested:
        resolved.require(name)
        if name not in ordered:
            ordered.append(name)
    return tuple(ordered)
