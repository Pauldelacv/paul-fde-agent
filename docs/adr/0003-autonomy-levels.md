# ADR 0003 — Autonomy levels map onto Hermes approvals, not a new engine

**Status:** Accepted · **Date:** 2026-09-01

## Problem

The project requires four autonomy levels (READ / PROPOSE / EXECUTE /
EXTERNAL). Hermes already has an approval system: `approvals.mode`
(`smart`/`manual`/`off`), `unattended_mode`, `cron_mode`, and fnmatch `deny`
globs, enforced inside the agent loop.

## Options

1. **Build a permission layer in `pfa` that wraps Hermes.** Full control over
   semantics. But `pfa` only sees the *launch*: once Hermes is running, every
   tool call happens inside a process we are not in. A check that cannot
   observe the call cannot block it. This would be security theatre.
2. **Define the levels as named presets over Hermes' real controls.** Less
   novel. Enforcement stays where it can actually work.

## Decision

Option 2. `AUTONOMY_LEVELS` maps each level to concrete `approvals` settings,
rendered into `$HERMES_HOME/config.yaml`. The unconditional `DENY_GLOBS` list
covers irreversible operations and is consulted before any approval mode.

## Invariants (asserted by tests)

- No level sets `unattended_mode` to anything but `deny`. Level 4 raises what
  the agent may *attempt*, never what it may do without a human present.
- No level sets `approvals.mode: off`. Hermes supports it; we do not expose it.

## Trade-off accepted

Our levels are only as strong as Hermes' approval implementation. That is the
correct dependency: the alternative was a check in the wrong process. Defence in
depth comes from the container backend, not from a second permission engine.
