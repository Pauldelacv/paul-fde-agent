# Architecture

## The question this project had to answer first

Hermes already provides the agent loop, 40+ tools, an MCP client, a skills
system, persistent memory, a cron scheduler, an approval system and seven
sandboxed execution backends. So: **what is left to build?**

Answering honestly is what keeps this repository small. If Paul FDE Agent
reimplemented any of that list, it would be a worse Hermes. It does not.

What Hermes does *not* have — verified in
[verified-facts.md](verified-facts.md) — is a way to say *"this user request is
a coding task, so send it to the strong model; that one is a summary, keep it
local and free."* Hermes routes its own internal side-tasks (context
compression, vision, title generation) through its `auxiliary` config, but the
user's request itself always goes to the session model.

That gap is this project's spine.

## Layers

```
        pfa CLI  ──►  routing policy  ──►  Decision (provider + model + why)
                                              │
                                              ▼
                            hermes chat --model <provider/model> --skills ...
                                              │
        ┌─────────────────────────────────────┼─────────────────────────┐
        ▼                                     ▼                         ▼
   Skills (SKILL.md)                    MCP servers               Memory (Hermes)
   FDE procedures                   lemlist / filesystem         sessions, recall
        │                                     │                         │
        └─────────────────────────────────────┴─────────────────────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    ▼                   ▼
                              Ollama / Gemma 4      Cloud LLM
                              (local, free)       (billed, stronger)
                                    │
                                    ▼
                        JSONL run log: model, duration, status, cost
```

Everything below the `hermes chat` line is Hermes. Everything above it is this
repository — roughly 1,300 lines of Python across eight modules.

## Where routing happens, and why there

The router runs **before** the agent starts, not during it. A Hermes session is
started with `--model <provider/model>`; the decision is therefore made once, at
launch, from the task text.

The alternatives were considered and rejected:

- **Patch Hermes** to route per-turn. Rejected: forking a 0.x project moving at
  a release every few days is a maintenance commitment with no exit.
- **An MCP tool the agent calls to pick its own model.** Rejected: a running
  Hermes session cannot swap its own model mid-flight in response to a tool
  result, so the tool would return advice nobody could act on.
- **Route at session launch.** Chosen: it uses a documented, stable flag; it
  costs nothing; the decision is inspectable before a token is spent
  (`pfa route`); and it is a pure function, so it is trivially testable.

The trade-off, stated plainly: a session that begins as research and turns into
coding halfway through stays on the research model. Mitigation today is
`pfa run --task coding` or simply starting a second session. If that friction
becomes real in daily use, the fix is per-turn routing, which needs upstream
support. See [ADR 0002](adr/0002-model-routing.md).

## Classification

Keyword rules, evaluated in policy order, first match wins, word-boundary
matched. Not an LLM classifier.

An LLM classifier would add a model call, latency and a new failure mode to
*every* request in order to choose between six buckets. Rules are free,
instant, deterministic and readable by the person who has to debug them — and
`--task` always overrides. The cost is real: rules miss phrasings that contain
no keyword, and those fall back to `default_task`. `pfa logs` makes that
visible, so the policy can be tuned from evidence rather than guesswork.

## Components

| Module | Responsibility |
|---|---|
| `config.py` | Load, expand `${VAR}`, validate the policy. Every error names the key and the remedy. |
| `router.py` | Pure classification and model resolution. No I/O. |
| `skills.py` | Discover, validate and install the procedure library; resolve the names a run will load. |
| `hermes.py` | Render `$HERMES_HOME/config.yaml`, define autonomy levels, build argv. |
| `runner.py` | Invoke Hermes as a subprocess, time it, record the outcome. |
| `observability.py` | JSONL run records, with redaction applied before every write. |
| `doctor.py` | Environment healthcheck. Reports SKIP where it cannot verify — never PASS. |
| `cli.py` | argparse surface. |

## Skills, and where attachment happens

The router produces a task category. That category is exactly the granularity at
which a standing procedure applies, so `routes.<task>.skills` in the policy names
the procedures preloaded for it, and they travel with the decision:
`pfa route` prints them before anything runs.

Two consequences are deliberate:

- **Names are resolved before Hermes launches.** A mistyped `--skill` costs an
  error message listing the real skills, not a session that quietly runs without
  the procedure it was supposed to follow. This holds on `--dry-run` too.
- **The config loader never touches the filesystem.** `routes.<task>.skills` is
  parsed as a list of names and nothing more, which keeps the policy a pure
  function of the file it was handed. Whether a named skill *exists* is checked
  where it can produce a useful message: `pfa doctor`, and the runner.

Getting the procedures to Hermes at all was the other Phase 2 problem. Hermes
reads `$HERMES_HOME/skills`, not this repository, and before Phase 2 nothing
reconciled the two: a procedure could be edited, committed and reviewed here and
never loaded by the running agent.

Re-checking the Hermes skills guide produced the better answer — `skills.
external_dirs` makes Hermes scan a directory in place — so the rendered config
points at `skills/` and there is no copy to fall behind. `pfa skills install`
remains for deployments where the repository is not on the agent's machine, and
`pfa doctor` covers both paths. It reads the *rendered* config rather than
re-rendering it, because Hermes silently skips an external directory that does
not resolve, and a check that confirms its own opinion confirms nothing. See
[ADR 0005](adr/0005-skill-library.md).

## Security posture

The agent runs model-generated commands. Two boundaries hold:

1. **Enforcement stays in Hermes.** Our four autonomy levels are a named mapping
   onto the real `approvals` block — `mode`, `unattended_mode`, `cron_mode` and
   `deny` globs. We do not build a second permission engine, because a
   permission check that does not sit inside the agent loop cannot actually stop
   a call. A test asserts no level ever sets `unattended_mode` to anything but
   `deny`, and no level disables approvals.
2. **Secrets are referenced, never copied.** The policy names environment
   variables; the rendered Hermes config emits `${VAR}`; the log writer redacts
   before writing. Three tests and a pre-push scanner enforce this.

See [security.md](security.md).

## What is deliberately not built yet

Phase 1 shipped the spine; Phase 2 shipped the skill library on top of it;
Phase 3 shipped the MCP connector policy and the lead-generation vertical. The
memory layer and the scheduled workflows are Phases 4–5, and the README roadmap
says so.

Building the abstraction before the second real use case exists is how
frameworks become unusable — which is also why `skills.py` did not exist in
Phase 1. One skill needs a path; five need a registry. `mcp.py` arrived the same
way: one connector is four lines of YAML, two connectors with credentials that
fail misleadingly need a loader that validates them.

Phase 3 also *removed* something from the plan. The roadmap had promised one
custom MCP server "to demonstrate the protocol end to end". lemlist publishes a
hosted one, so ours would have been a process to run and a protocol to keep
current in exchange for nothing. The promise is withdrawn and marked as such
rather than deferred — see [ADR 0006](adr/0006-mcp-connectors.md). Subtraction
was the right answer in Phase 1 too, when the question was what remains once
Hermes' own capabilities are taken out.

### The one place the architecture bends for a non-technical reason

Every route in `config/routing.yaml` is chosen on cost and capability, except
`prospecting`, which is pinned to the local model because a prospect list is
personal data. A hosted model would write better copy and would also add a
processor to contract with and a transfer to document. That is a legal
constraint expressed as a routing decision, and it is worth naming as such:
[ADR 0007](adr/0007-lead-generation.md).
