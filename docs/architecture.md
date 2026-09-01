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
   FDE procedures                  GitHub / Postgres / web        sessions, recall
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
| `hermes.py` | Render `$HERMES_HOME/config.yaml`, define autonomy levels, build argv. |
| `runner.py` | Invoke Hermes as a subprocess, time it, record the outcome. |
| `observability.py` | JSONL run records, with redaction applied before every write. |
| `doctor.py` | Environment healthcheck. Reports SKIP where it cannot verify — never PASS. |
| `cli.py` | argparse surface. |

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

Phase 1 ships the spine. The FDE skill library, the MCP connectors, the memory
layer and the scheduled workflows are Phases 2–5, and the README roadmap says so.
Building the abstraction before the second real use case exists is how frameworks
become unusable.
