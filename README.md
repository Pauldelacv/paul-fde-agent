# Paul FDE Agent

**A self-hosted agent for Forward Deployed Engineering work — built on the
Hermes Agent runtime, running local Gemma 4 by default and routing to a cloud
model only when the task actually needs one.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11--3.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-132%20passing-brightgreen.svg)](tests/)

> **Status: Phase 1 (Foundation) complete.** The routing spine, CLI, Hermes
> integration, Docker deployment, security tooling and test suite are working
> and tested. The FDE skill library, MCP connectors, memory layer and scheduled
> workflows are Phases 2–5 — see the [Roadmap](#roadmap). Nothing in this README
> describes a feature that does not exist; where something is planned, it says so.

---

## 1. What is Paul FDE Agent?

A framework for running Forward Deployed Engineer tasks — debugging a client
integration, researching a technical landscape, analysing a repository,
preparing a client briefing — through an agent you host yourself.

It is a **thin, deliberate layer over [Hermes Agent](https://github.com/NousResearch/hermes-agent)**,
not a re-implementation of it. Hermes supplies the agent loop, tools, MCP
client, memory, cron and approvals. This project supplies the piece Hermes does
not have: **routing each task to the right model**, plus the FDE-specific
skills, security posture and operational tooling around it.

Roughly 1,300 lines of Python. That number is a design goal, not an accident.

## 2. Why it exists

Three problems, in order of how much they cost:

**Cost.** Running every request against a frontier model is the default and it
is expensive. Most daily FDE work — summarising a thread, drafting notes,
triaging logs, first-pass research — does not need a frontier model. Some of it
genuinely does. The difference between those two cases is worth real money over
a year of freelance work.

**Privacy.** Client context is the substance of FDE work, and much of it should
not leave a machine you control. A local model is not a cost optimisation there;
it is the only acceptable option.

**Repeatability.** Good FDE work is methodical: reproduce, hypothesise, test,
distinguish fact from assumption. That method should live in version-controlled
procedures the agent follows, not in whatever the model improvises today.

The gap this fills concretely: Hermes routes its own *internal* side-tasks
(context compression, vision, title generation) to configurable models, but the
user's request always goes to the session model. There is no "this is a coding
task, use the strong model" layer. That is what this project adds.

## 3. Architecture

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
repository.

Routing happens **before** the session starts, using the documented
`--model provider/model` flag. Full reasoning, including the two rejected
alternatives and the trade-off accepted, is in
[docs/architecture.md](docs/architecture.md) and
[ADR 0002](docs/adr/0002-model-routing.md).

## 4. Features

**Working now (Phase 1):**

- **Task-category model routing** — six categories, keyword-classified,
  overridable, inspectable before a token is spent.
- **`pfa route`** — shows the decision *and its basis* without running anything.
- **`pfa doctor`** — full environment healthcheck with a remedy per failure;
  reports SKIP rather than PASS for anything it cannot verify.
- **Four autonomy levels** mapped onto Hermes' real approval controls, with an
  unconditional deny list for irreversible operations.
- **Structured JSONL run logs** with credential redaction applied before write.
- **Docker Compose stack** — agent + Ollama + Postgres, healthchecks, non-root,
  named volumes.
- **Secret-leak prevention** — layered `.gitignore`, a shape-based scanner, and
  security tests that fail the build.
- **132 tests**, no network access, no real credentials.

**Planned:** FDE skill library, MCP connectors, persistent memory, scheduled
workflows. See the [Roadmap](#roadmap).

## 5. Installation

```bash
git clone https://github.com/pauldelacv/paul-fde-agent.git
cd paul-fde-agent
python3 -m venv .venv && source .venv/bin/activate
make install-hermes
cp .env.example .env && chmod 600 .env
$EDITOR .env
pfa doctor
```

Requires Python 3.11–3.13 (the range Hermes supports).

## 6. Local development

```bash
make install     # dev dependencies only, no Hermes runtime
make test        # 132 tests, ~1s, no network
make lint        # ruff check + format check
make check       # everything CI runs
make doctor
make secrets-check   # run before every push
```

The suite runs without Hermes installed: the subprocess boundary is stubbed, so
routing, config, redaction and CLI behaviour are all testable in isolation.

## 7. VPS deployment

```bash
cp .env.example .env && chmod 600 .env   # POSTGRES_PASSWORD is mandatory
make up
make pull-models
make ps
```

Full guide, backups and recovery: [docs/deployment.md](docs/deployment.md).

## 8. Gemma 4 setup

Gemma 4 (Google DeepMind, 2 April 2026, Apache 2.0) has **native function
calling** — the capability that makes it usable as an agent backend at all.

```bash
make pull-models          # gemma4:e2b and gemma4:e4b
```

**Size is the real constraint.** Approximate, Q4_K_M, CPU-only:

| Variant | Download | RAM | Small CPU VPS? |
|---|---|---|---|
| `gemma4:e2b` | ~7.2 GB | ~6 GB | Yes |
| `gemma4:e4b` | ~9.6 GB | ~10 GB | Yes, with ≥12 GB |
| `gemma4:26b` MoE | ~18 GB | ~20 GB | Large instances only |
| `gemma4:31b` dense | ~20 GB | ~24 GB | GPU, realistically |

The shipped policy routes `debugging` to `gemma4:26b`, which **will be unusably
slow on a small VPS**. Change that route to `e4b` or to `cloud` — see
[docs/deployment.md](docs/deployment.md#sizing).

## 9. Model routing

`config/routing.yaml` is the whole policy. Nothing is hardcoded.

```yaml
routes:
  simple:         { provider: local, model: "gemma4:e2b" }
  summarization:  { provider: local, model: "gemma4:e4b" }
  research:       { provider: local, model: "gemma4:e4b" }
  debugging:      { provider: local, model: "gemma4:26b" }
  coding:         { provider: cloud, model: null }   # null = provider default
  architecture:   { provider: cloud, model: null }
```

Inspect a decision before spending anything:

```console
$ pfa route "Research the latest developments in MCP"
research -> local/gemma4:e4b [local (no per-token cost)] (matched keyword 'research')

$ pfa route "Implement this issue in a branch"
coding -> cloud/anthropic/claude-sonnet-4.5 [cloud (billed)] (matched keyword 'implement')

$ pfa route "What time is it in Tokyo"
simple -> local/gemma4:e2b [local (no per-token cost)] (no rule matched; fell back to default_task)
```

Override classification with `pfa run --task coding "..."`.

Classification is keyword rules, not an LLM classifier — an extra model call on
every request to choose between six buckets is a poor trade. Rules are free,
deterministic and debuggable. Cost accepted: unphrased tasks fall back to the
cheapest route, and `pfa logs` shows how often that happens so the policy can be
tuned from evidence. See [ADR 0002](docs/adr/0002-model-routing.md).

## 10. MCP

Hermes is MCP-native: servers are declared under `mcp_servers` in
`$HERMES_HOME/config.yaml`, over stdio, HTTP or OAuth 2.1. Adding one:

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/srv/work"]
```

or `hermes mcp add <name>`.

**Phase 1 ships no MCP connectors and no custom server.** The existing GitHub,
Postgres and filesystem servers already do the job, and writing wrappers around
them would be exactly the premature abstraction this project is trying to avoid.
Phase 3 adds the connector configuration and one minimal custom server built to
demonstrate the protocol end to end. Until then, this section describes Hermes'
capability, not ours.

## 11. Skills

Skills are procedures in [agentskills.io](https://agentskills.io) format —
portable across Hermes installations, version-controlled, and reviewable.

```
skills/fde/fde-methodology/SKILL.md
```

Phase 1 ships **one** skill: [`fde-methodology`](skills/fde/fde-methodology/SKILL.md),
the 13-step procedure for taking a problem from "something is broken" to a
root cause and a client-readable summary. Its central rule is that every
statement must be labelled **FACT**, **HYPOTHESIS**, **CONCLUSION**,
**ACTION TAKEN** or **ACTION RECOMMENDED** — and a hypothesis is never promoted
to a fact because it is plausible or because time is short.

It ships alone on purpose: one skill proves the format works end to end, and
the remaining categories (research, GitHub, API integration, technical writing)
are Phase 2, written against real use rather than guessed at in advance.

```bash
pfa run --skill fde-methodology "The client's webhook sync stopped last Tuesday"
```

## 12. Memory

Hermes provides persistent cross-session memory, FTS5 session search with LLM
summarisation, and agent-curated recall. It lives in `$HERMES_HOME`, which is a
Docker volume in the deployed stack.

**Phase 1 does not extend it.** The project-scoped, inspectable, exportable
memory model — working / episodic / semantic / project — is Phase 4, and needs
the Postgres service the compose file already provisions. Today, memory is
whatever Hermes gives you.

## 13. Security

This repository is public and the agent executes model-generated commands. Both
facts are taken seriously.

**Keeping secrets out:** layered `.gitignore`; `make secrets-check` scanning
tracked files for credential *shapes* (not keywords); security tests asserting
`.env` is untracked, `.env.example` holds only placeholders and documents every
variable the policy references, and no skill contains a credential; redaction
applied to every log record before it is written; and a rendered Hermes config
that emits `${VAR}` references rather than values.

**Constraining the agent:** four autonomy levels mapped onto Hermes' real
`approvals` controls — because a permission check outside the agent loop cannot
actually block a call.

| Level | Name | Meaning |
|---|---|---|
| 1 | READ | Read and analyse only |
| 2 | PROPOSE | Draft actions, confirm each (**default**) |
| 3 | EXECUTE | Reversible actions unattended; risky patterns still prompt |
| 4 | EXTERNAL | External/destructive targets, explicit confirmation required |

Two invariants, both asserted by tests: **no level ever permits unattended
destructive action**, and **no level disables approvals**. An unconditional deny
list covers `rm -rf /`, `DROP DATABASE`, `git push --force`, `terraform destroy`
and similar, refused before any approval mode is consulted.

**Prompt injection is not solved** — no honest agent project claims otherwise.
The mitigations and their limits are set out in [docs/security.md](docs/security.md).

## 14. Scheduled workflows

Hermes has a built-in cron scheduler: jobs in `~/.hermes/cron/jobs.json`, skills
attachable per job, results deliverable to multiple targets.

```bash
hermes cron create "0 8 * * *" "Prepare my morning FDE briefing" --skill fde-methodology
```

**Phase 5** adds the morning briefing, weekly AI research and prospect
monitoring workflows on top of it. Prospect and client lists are configuration,
never repository content — `prospects.*` and `clients/` are gitignored and a
test asserts they stay untracked.

## 15. Examples

```bash
# See where a task would go, and why — costs nothing
pfa route "Analyse this repository and find the documentation gaps"

# Run it (local model, free)
pfa run "Research the latest developments in MCP and what matters for a freelance FDE"

# Force the strong model regardless of phrasing
pfa run --task architecture "Should we put a queue between these two services?"

# Run with the FDE methodology procedure loaded
pfa run --skill fde-methodology "Debug this API integration"

# Validate a policy change without spending anything
pfa run --dry-run "Prepare my morning FDE briefing"

# Inspect what has been run, on which model, at what cost
pfa logs --limit 20
```

Configuration and diagnostics:

```bash
pfa config                                  # resolved policy; never prints a key
pfa doctor --json                           # machine-readable health
pfa autonomy                                # explain the four levels
pfa hermes-config --autonomy read --write   # render $HERMES_HOME/config.yaml
```

## 16. Development

```
src/pfa/         config, router, hermes integration, runner, observability, doctor, cli
config/          routing.yaml — the whole policy
skills/          agentskills.io-format procedures
docker/          Dockerfile + compose stack
docs/            architecture, security, deployment, verified-facts, ADRs
tests/           132 tests: config, routing, hermes, runner, observability, security, CLI
scripts/         check-secrets.sh
```

**One runtime dependency: `PyYAML`.** argparse instead of click, a hand-written
validator instead of pydantic, urllib instead of requests. Each rejection is
justified in [ADR 0004](docs/adr/0004-minimal-dependencies.md). The goal is a
repository a stranger can read in an afternoon.

Before pushing: `make check && make secrets-check`.

Architectural changes get an ADR in `docs/adr/`: the problem, 2–3 options, the
choice, and the trade-off accepted.

### On verification

Every external claim — Hermes version numbers, config schema, CLI flags, Gemma 4
sizes — is recorded with its source and check date in
[docs/verified-facts.md](docs/verified-facts.md).

Notably: **the brief for this project specified "Hermes Agent 2.x", which does
not exist.** The project is at v0.21.0 (PyPI publishes 0.19.0). This repository
targets 0.19–0.21 and says so rather than quietly inventing a version.

## 17. Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation — structure, config, Docker, Hermes integration, local models, healthcheck, CLI | **Complete** |
| 2 | FDE skills — debugging, research, GitHub, API integration, technical writing | Next |
| 3 | MCP — GitHub, Postgres, filesystem, web research, one custom server | Planned |
| 4 | Memory — persistent, project-scoped, episodic, retrieval | Planned |
| 5 | Automation — morning briefing, research reports, prospect monitoring | Planned |
| 6 | Routing — cost tracking from real token counts, smarter classification | Planned |
| 7 | Production — reverse proxy, secret management, backups, monitoring | Planned |
| 8 | Portfolio — diagrams, demos, case study | Planned |

---

## Why this matters for FDE

Forward Deployed Engineering is landing in an unfamiliar system, under time
pressure, and being useful without breaking anything. This project is built the
way that job has to be done, and the code is the evidence:

**Verify before building.** The brief named a version of Hermes that does not
exist. Finding that out took four minutes and is recorded in
`docs/verified-facts.md` with sources. Shipping against an imagined API is how
an integration fails in week three.

**Know what you are standing on.** The first architectural decision was
subtractive: Hermes already has the loop, tools, MCP, memory, cron and
approvals, so the honest question was what remains. The answer was task-level
model routing. Everything else would have been a worse copy.

**Put controls where they can work.** The autonomy levels map onto Hermes'
approval system rather than wrapping it, because a permission check outside the
agent loop cannot block a tool call — it can only look like it does. Choosing
the less impressive design because it is the one that functions is most of the
job.

**Separate fact from hypothesis.** The `fde-methodology` skill enforces it, and
so does the code: `pfa route` reports *why* it chose a model; `pfa doctor`
reports SKIP rather than PASS for anything it cannot verify; the router's
explanation says "no rule matched" instead of implying intent. Confidently wrong
is the expensive failure mode with clients.

**Make cost and risk visible.** Every run is logged with model, duration and
status. Every credential path is scanned before it can be pushed. Both are
things a client eventually asks about.

**Leave something maintainable.** One runtime dependency, ADRs for every real
decision, and 132 tests that run in a second without network or credentials.
The measure of an FDE engagement is what still works after you leave.

---

**License:** [MIT](LICENSE)
