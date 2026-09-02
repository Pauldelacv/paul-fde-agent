---
name: github-workflow
description: Procedure for working in someone else's repository - analysis, issues, branches, commits and pull requests - without breaking their conventions
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, github, git, code-review, repository]
    category: fde
---

# GitHub Workflow

A procedure for landing in an unfamiliar repository and being useful in it
without breaking anything or leaving a mess behind.

## When to Use

Use this for repository analysis, issue triage, implementing a change in a
client's codebase, opening or reviewing a pull request. The defining condition
is that **the repository is not yours**: its conventions outrank your habits,
and the people who maintain it will live with the result after you leave.

## The Non-Negotiable Rules

1. **Never commit to the default branch.** Not for a one-line change, not
   because the change is obviously correct, not because time is short.
2. **Never rewrite published history.** No force-push, no amend, no rebase on a
   branch anyone else may have checked out. On your own unpublished branch,
   follow whatever the repository already does.
3. **Never commit a credential.** Check the diff, not your intention. `git diff
   --cached` before every commit, every time.
4. **Read the repository's own rules first** — `CONTRIBUTING.md`, `CLAUDE.md`,
   `AGENTS.md`, the PR template, the CI config. They outrank this file.
5. **Respect the configured autonomy level.** At PROPOSE, you draft the branch,
   the commit and the PR body and ask before each one lands. Pushing is an
   outward-facing action: it is visible to other people the moment it happens.

## Procedure

### Understanding a repository

1. **Read the entry points, in this order:** `README.md`, `CONTRIBUTING.md`, the
   CI workflow files, the build/task file (`Makefile`, `package.json` scripts,
   `pyproject.toml`), then the test directory. CI is the most honest document in
   any repository: it says what is actually enforced, as opposed to what the
   README hopes for.
2. **Establish scale before opinion.** File count, language mix, test count,
   dependency count, date of the last commit, number of active contributors. A
   recommendation that ignores the size of the thing it applies to is noise.
3. **Read the history for convention.** `git log --oneline -30` shows commit
   message style; `git log --merges` shows whether they merge or rebase; branch
   names show the naming scheme. Match what you find.
4. **Find the boundaries.** What is generated, what is vendored, what is
   deliberately untested. Changing generated files by hand is a classic
   outsider mistake.

### Making a change

5. **Reproduce the current state first.** Run the repository's own checks
   (`make check`, `npm test`, `pytest`) *before* touching anything. If they
   already fail, that is a FACT to report, not a mystery to inherit.
6. **Branch from the current default branch**, freshly fetched. Name it in the
   repository's scheme, or `<type>/<short-description>` if there is none.
7. **Make the smallest change that solves the stated problem.** Adjacent
   improvements you notice go in the PR description as ACTION RECOMMENDED, not
   into the diff. Widening a PR unasked is how an outsider's change stops being
   reviewable.
8. **Match the surrounding code.** Its naming, its comment density, its error
   handling, its test style. A change that reads as foreign gets reviewed on
   style instead of substance.
9. **Add or update the test that would have caught this.** For a bug fix, show
   the test failing before and passing after. A fix with no such test is an
   assertion.
10. **Run the repository's checks again**, all of them, before committing.
11. **Commit in reviewable units** with messages in the repository's style —
    typically a subject line under ~72 characters saying what changed and why,
    not what file was edited.

### Opening a pull request

12. **Use the repository's PR template** if one exists; fill in every section it
    asks for. If there is none, cover: what changed, why, how it was verified,
    and what the reviewer should look at hardest.
13. **State the blast radius and the rollback.** What breaks if this is wrong,
    and how to undo it.
14. **List what you did not do**, and why — the adjacent problems you found and
    deliberately left alone.
15. **Wait for CI, and read it.** A PR left red is not delivered. If a failure
    is unrelated to your change, prove it (reproduce it on the base branch) and
    say so in the PR rather than asserting "flaky".

### Reviewing

16. **Correctness first**, then tests, then clarity, then style. Style comments
    on a PR with a correctness bug waste everyone's turn.
17. **Distinguish blocking from optional.** Label each comment. An unlabelled
    pile of comments is impossible for an author to triage.
18. **Say what you verified.** "I ran the branch and reproduced the fix" is
    worth ten approving comments that only read the diff.

## Output Template

```
## Repository
<name> — <language/stack>, <N> files, <N> tests, last commit <date>
Conventions observed: branch naming <x>, commits <style>, CI enforces <what>

## Change
FACT: current behaviour is <x> — established by <command/test>
ACTION TAKEN: <what changed, in which files>
Verification: <check run> — before: <result>, after: <result>

## Pull request
Branch: <name> (from <base>, fetched <date>)
Blast radius: <what this can break>
Rollback: <how to undo>

## Deliberately not done
- ACTION RECOMMENDED: <adjacent issue found> — why left alone: <reason>

## Open questions for the maintainer
- <question the diff cannot answer>
```

## Pitfalls

- Committing to the default branch "just this once".
- Reformatting files the change does not otherwise touch, which buries the real
  diff under whitespace.
- Editing generated or vendored files by hand.
- Opening a PR whose description explains *what* the diff shows and not *why*.
- Force-pushing to a branch someone else has checked out.
- Fixing an unrelated bug in the same PR because it was right there.
- Claiming a CI failure is a flake without reproducing it on the base branch.
- Reporting "the codebase is well structured" — a judgement with no evidence
  behind it is filler.

## Verification

Before delivering, check: the branch is not the default branch; `git diff` has
been read line by line; the repository's own checks pass; every claim about the
repository names the command that established it; the "deliberately not done"
section exists.
