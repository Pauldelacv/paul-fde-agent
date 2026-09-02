# ADR 0005 — Attach skills to task categories in the routing policy

**Status:** Accepted · **Date:** 2026-09-02

## Problem

Phase 2 takes the skill library from one procedure to five. Two questions
follow, and Phase 1 answered neither.

**How does a skill get loaded?** Phase 1's only answer was `pfa run --skill
fde-methodology`, typed by hand. A procedure that has to be remembered is a
procedure that gets skipped on the day it matters — which is the busy day, which
is the day it was written for.

**How does a skill reach the agent at all?** Hermes reads skills from
`$HERMES_HOME/skills/<category>/<name>/SKILL.md`. This repository stores them in
`skills/`. Nothing reconciled the two, so a procedure could be edited here,
committed, reviewed, and never loaded by the running agent. That is a silent
failure, and this project's whole posture is that silent failures are the
expensive kind.

## Options

1. **Leave attachment manual.** Zero new machinery. Also zero help on the day it
   matters, and it leaves the install gap unaddressed.
2. **Let the model choose its own skills.** Hermes can already discover skills
   at runtime. But the choice then happens inside the session, invisibly, on the
   same small local model whose judgement the procedure exists to scaffold —
   and it cannot be inspected before a token is spent.
3. **Declare attachment in the routing policy**, as `routes.<task>.skills`. The
   router already classifies each task; the category it produces is exactly the
   granularity at which a standing procedure applies.

## Decision

Option 3, plus pointing Hermes at the library where it already lives.

`routes.<task>.skills` lists the procedures preloaded for that category. They
are merged with anything passed via `--skill` (policy order first, extras after,
duplicates dropped) and passed to `hermes chat --skills`. `pfa route` prints
them before anything runs; `--no-auto-skills` suppresses them without changing
which model is selected.

### Reaching the agent: scan in place, do not copy

Re-checking the Hermes skills guide (2026-09-02, recorded in
`verified-facts.md`) turned up `skills.external_dirs` — additional directories
Hermes scans alongside its own. That is strictly better than copying, so
`pfa hermes-config --write` now emits:

```yaml
skills:
  enabled: true
  external_dirs: ["/abs/path/to/repo/skills"]
```

Hermes then reads the procedures where they are version-controlled. There is no
second copy, so there is nothing to fall behind. `pfa skills install` remains
for the case the config cannot cover — the agent running somewhere the
repository is not, such as a container without the source mounted.

Two verified details shaped the check rather than merely the config:

- **A non-existent external dir is silently skipped.** "Configured" therefore
  does not imply "working", so `pfa doctor` reads the rendered `config.yaml` and
  confirms a declared path actually resolves to the library — rather than
  re-rendering it and confirming its own opinion.
- **External dirs are not a write-protection boundary.** If Hermes can write to
  the directory, the agent can rewrite its own procedures — in a git working
  tree, silently. The compose stack already mounts `../skills` read-only; that
  mount is now load-bearing rather than incidental, and `docs/security.md` says
  so.

Names are resolved against the library **before** Hermes is launched. A mistyped
`--skill` costs an error message naming the real skills, not a session that
quietly runs without the procedure it was supposed to follow. This holds on the
`--dry-run` path too: a dry run that skipped validation would not check the
thing most likely to be wrong.

### What is not attached, and why

`api-integration` is explicit-only. It applies when the problem is an
integration, not whenever something is broken, and `debugging` is a category
where most tasks are neither. A procedure loaded for every task in a category
and relevant to a tenth of them spends context to make the model less focused.

The rule the policy follows: **attach a skill only if it applies to the whole
category.** Anything narrower stays a `--skill` away.

## Trade-offs accepted

- **The attachment is per-category, not per-task.** Both `summarization` and
  `architecture` get `technical-writing`, which is right for an ADR and slightly
  heavy for a three-line recap. The skill is written to scale (its *Sizing*
  section says so), and the alternative — a second classifier for procedures —
  costs more than it returns.
- **Attachment inherits classification's errors.** A task that keyword-matches
  the wrong category now gets the wrong procedure as well as the wrong model.
  This makes misclassification more visible rather than more costly: `pfa route`
  shows both before anything runs, and `pfa logs` records what was attached.
- **The copy path can still drift**, for deployments that use `pfa skills
  install` instead of `external_dirs`. Install is a step someone has to run; it
  is not automatic on every run, because silently writing into `$HERMES_HOME`
  behind the operator's back is worse than a `WARN` from `pfa doctor` that names
  the drifted skill and the one command that fixes it.
- **A Hermes-local skill of the same name shadows ours.** Local precedence is
  documented and we do not fight it: the names in this library are specific
  enough (`fde-methodology`, not `debugging`) that a collision would be a
  deliberate override, which is the behaviour someone would want.
- **Validation is duplicated with Hermes.** Hermes parses `SKILL.md` too. We
  validate anyway, because the failure we care about is the one where Hermes
  quietly loads nothing, and a check that only runs inside the runtime cannot
  report on a repository.

## Why the config loader does not check the filesystem

`routes.<task>.skills` is parsed as a list of names and nothing more. The loader
never asks whether those skills exist. Keeping it a pure function of the file it
was handed is what lets the policy stay testable without a library on disk, and
lets `pfa skills` keep working when the thing being debugged is the policy.

Existence is checked where it can produce a useful message instead: `pfa doctor`
before the run, and the runner at the moment of the run.
