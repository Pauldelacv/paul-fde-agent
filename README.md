# Paul FDE Agent

**A self-hosted agent for Forward Deployed Engineering work — built on the
Hermes Agent runtime, running local Gemma 4 by default and routing to a cloud
model only when the task actually needs one.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11--3.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-322%20passing-brightgreen.svg)](tests/)

> **Status: Phases 1–3 complete.** The routing spine, CLI, Hermes integration,
> Docker deployment, security tooling and test suite work (Phase 1); the FDE
> skill library — eight procedures, attached to task categories by policy,
> validated and installable — works (Phase 2); MCP connectors and the
> lead-generation vertical work (Phase 3). The memory layer and scheduled
> workflows are Phases 4–5 — see the [Roadmap](#18-roadmap). Nothing in this README
> describes a feature that does not exist; where something is planned, it says
> so, and where a plan was dropped it says that too.

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

Roughly 3,200 lines of Python. That number is a design goal, not an accident.

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
repository.

Routing happens **before** the session starts, using the documented
`--model provider/model` flag. Full reasoning, including the two rejected
alternatives and the trade-off accepted, is in
[docs/architecture.md](docs/architecture.md) and
[ADR 0002](docs/adr/0002-model-routing.md).

## 4. Features

**Working now (Phases 1–3):**

- **Task-category model routing** — seven categories, keyword-classified,
  overridable, inspectable before a token is spent.
- **A lead-generation agent** — sources and enriches prospects through the
  lemlist MCP connector, refuses to touch a prospect with no recorded
  provenance or an objection on file, and writes one personalised draft per
  person. **It has no send path.** See [Lead generation](#12-lead-generation).
- **MCP connectors as configuration** — declared in `config/mcp.yaml`,
  validated, and rendered into the Hermes config with credentials passed
  through as `${VAR}` references rather than values.
- **Eight FDE skills**, attached to task categories by the policy rather than
  remembered by hand: debugging methodology, technical research, GitHub
  workflow, API integration, technical writing, lead generation, GDPR
  compliance, outreach writing.
- **`pfa skills`** — list, inspect, validate and install the library; a mistyped
  `--skill` fails before a token is spent, not silently.
- **`pfa route`** — shows the decision, its basis *and the procedures it
  attaches*, without running anything.
- **`pfa doctor`** — full environment healthcheck with a remedy per failure;
  reports SKIP rather than PASS for anything it cannot verify.
- **Four autonomy levels** mapped onto Hermes' real approval controls, with an
  unconditional deny list for irreversible operations.
- **Structured JSONL run logs** with credential redaction applied before write,
  and no task text — a drafting prompt names a real person.
- **Docker Compose stack** — agent + Ollama + Postgres, healthchecks, non-root,
  named volumes, and a one-command `make deploy`.
- **Secret-leak prevention** — layered `.gitignore`, a shape-based scanner, and
  security tests that fail the build.
- **322 tests**, no network access, no real credentials.

**Planned:** persistent memory, scheduled workflows. See the
[Roadmap](#18-roadmap).

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
make test        # 322 tests, ~2s, no network
make lint        # ruff check + format check
make check       # everything CI runs
make doctor
make skills          # list the skill library
make mcp             # list the MCP connectors and their credential state
make secrets-check   # run before every push
```

The suite runs without Hermes installed: the subprocess boundary is stubbed, so
routing, config, redaction and CLI behaviour are all testable in isolation.

## 7. VPS deployment

```bash
cp .env.example .env && chmod 600 .env   # POSTGRES_PASSWORD is mandatory
make deploy                              # build, start, pull models, render config, verify
```

`make deploy` finishes with `make smoke`, which proves the deployed stack works
without spending a token: `pfa doctor`, `pfa mcp`, a routing decision, skill
validation, and a dry run through the whole path.

Needs 12 GB RAM and ~15 GB disk. Full guide, sizing, backups and recovery:
[docs/deployment.md](docs/deployment.md).

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

The shipped policy uses `e4b` for every local route, so it runs on the machine
this project is built to be deployed on. Raise `debugging` to `26b` or send it
to the cloud if your host can carry it — see
[docs/deployment.md](docs/deployment.md#sizing).

## 9. Model routing

`config/routing.yaml` is the whole policy. Nothing is hardcoded.

```yaml
routes:
  simple:         { provider: local, model: "gemma4:e2b", skills: [] }
  summarization:  { provider: local, model: "gemma4:e4b", skills: [technical-writing] }
  research:       { provider: local, model: "gemma4:e4b", skills: [technical-research] }
  debugging:      { provider: local, model: "gemma4:e4b", skills: [fde-methodology] }
  prospecting:    { provider: local, model: "gemma4:e4b", skills: [lead-generation, gdpr-compliance] }
  coding:         { provider: cloud, model: null, skills: [github-workflow] }
  architecture:   { provider: cloud, model: null, skills: [technical-writing] }
```

`prospecting` is the one route where the provider is a **compliance** decision
rather than a cost one. A prospect list is personal data; keeping it on the box
means there is no processor to contract with and no transfer to document. The
cost is stated plainly in the policy file: e4b writes weaker copy than a
frontier model, and changing it is one line with three obligations attached.

`model: null` means the provider's default. `skills:` names the procedures
preloaded for that category — see [Skills](#11-skills).

Inspect a decision before spending anything:

```console
$ pfa route "Research the latest developments in MCP"
research -> local/gemma4:e4b [local (no per-token cost)] (matched keyword 'research') + skills: technical-research

$ pfa route "Implement this issue in a branch"
coding -> cloud/anthropic/claude-sonnet-4.5 [cloud (billed)] (matched keyword 'implement') + skills: github-workflow

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

Hermes owns the MCP client — transports, discovery, filtering, OAuth. This
project owns the **policy**: which servers the agent may reach, which of their
tools it may see, and which credential each one needs. That lives in
`config/mcp.yaml` and is rendered into `mcp_servers` by
`pfa hermes-config --write`.

```yaml
servers:
  lemlist:
    transport: http
    url: "https://app.lemlist.com/mcp?bucket=prospecting"
    headers:
      X-API-Key: "${LEMLIST_API_KEY}"
    requires_env: [LEMLIST_API_KEY]
    tools:
      exclude: ["*send_*", "*launch*", "*delete_*"]
```

```console
$ pfa mcp
  lemlist     http   ready
              https://app.lemlist.com/mcp?bucket=prospecting
              Prospect sourcing, email enrichment and campaign leads. …
  filesystem  stdio  NEEDS $PFA_WORKSPACE_DIR
```

**The credential is never expanded here.** `${VAR}` survives into
`$HERMES_HOME/config.yaml` so Hermes resolves it at connect time, which keeps the
rendered file safe to read, diff and back up. A test sets a real-looking key in
the environment and asserts it does not appear in the output.

That passthrough has a documented failure mode worth knowing about: **Hermes
keeps an unset `${VAR}` verbatim and only logs a warning**, so a connector with
no key does not fail to start — it authenticates with the literal text
`${LEMLIST_API_KEY}` and gets a 401 that reads like a revoked key. Two guards:
`pfa doctor` and `pfa mcp` report it before a connection is attempted, and the
loader refuses any server referencing a variable it has not declared in
`requires_env`.

### What is deliberately not here

**No custom MCP server.** Earlier plans promised one "to demonstrate the
protocol end to end". lemlist publishes a hosted MCP server, so connecting to it
is a URL and a header; writing our own to sit in front of it would add a process
to run and a protocol to keep current, in exchange for nothing. The promise is
withdrawn rather than deferred — see [ADR 0006](docs/adr/0006-mcp-connectors.md).

**No GitHub connector.** Hermes' own documentation says GitHub is excluded from
its catalogue deliberately, because its bundled `github/*` skills driving the
`gh` CLI are the better integration.

**No Postgres connector yet.** The compose stack provisions Postgres for the
Phase 4 memory layer. A connector to a database nothing writes to is surface
area with no user; it arrives with the memory layer.

## 11. Skills

Skills are procedures in [agentskills.io](https://agentskills.io) format —
portable across Hermes installations, version-controlled, and reviewable. The
layout is Hermes' own, so nothing here is a project-specific dialect:

```
skills/<category>/<name>/SKILL.md
```

**Eight ship today** ([library README](skills/README.md)):

| Skill | What it is for | Attached to |
|---|---|---|
| [`fde-methodology`](skills/fde/fde-methodology/SKILL.md) | 13 steps from "something is broken" to a root cause and a client-readable summary | `debugging` |
| [`technical-research`](skills/fde/technical-research/SKILL.md) | Landscape reviews and veille that produce sourced, dated claims — with a source hierarchy and an explicit "not verified" section | `research` |
| [`github-workflow`](skills/fde/github-workflow/SKILL.md) | Working in a repository that is not yours: conventions, branches, PRs, review | `coding` |
| [`api-integration`](skills/fde/api-integration/SKILL.md) | Third-party APIs: contract vs. observed behaviour, error taxonomy, idempotency, webhooks | explicit only |
| [`technical-writing`](skills/fde/technical-writing/SKILL.md) | Client summaries, decision records, handovers a non-specialist can act on | `summarization`, `architecture` |
| [`lead-generation`](skills/fde/lead-generation/SKILL.md) | ICP to sourcing to enrichment to verified, researched drafts — with the compliance gate built into the pipeline | `prospecting` |
| [`gdpr-compliance`](skills/fde/gdpr-compliance/SKILL.md) | Legal basis, Article 14 notice, rights, retention, processors and transfers — a procedure, explicitly not legal advice | `prospecting` |
| [`outreach-writing`](skills/fde/outreach-writing/SKILL.md) | A cold message a specific person would answer: evidence-based personalisation, one ask, no invented familiarity | explicit only |

Every one inherits the same rule: **label each statement** — FACT, HYPOTHESIS,
CONCLUSION, ACTION TAKEN, ACTION RECOMMENDED — and never promote a hypothesis to
a fact because it is plausible or because time is short.

### Attachment is policy, not habit

A procedure you have to remember to type is one that gets skipped on the day it
matters. `routes.<task>.skills` in `config/routing.yaml` declares which
procedures load for which category, so the router that already picked the model
also picks the method:

```console
$ pfa route "The client's webhook sync stopped last Tuesday"
debugging -> local/gemma4:26b [local (no per-token cost)] (matched keyword 'webhook') + skills: fde-methodology
```

Extras stack on top; `--no-auto-skills` opts out. A skill is attached only if it
applies to the *whole* category — `api-integration` stays explicit because most
debugging tasks are not integration problems. Reasoning in
[ADR 0005](docs/adr/0005-skill-library.md).

### Managing the library

```bash
pfa skills                       # list, with where each one attaches
pfa skills show fde-methodology  # print one in full
pfa skills validate              # exits 1 if any skill is malformed
pfa hermes-config --write        # point Hermes at skills/ where it lives
pfa skills install               # or copy into $HERMES_HOME/skills, if it cannot
pfa run --skill api-integration "The webhook signature check started failing"
```

**Hermes reads the library in place.** `pfa hermes-config --write` emits
`skills.external_dirs: [<abs path>/skills]`, so the agent loads the procedures
from where they are version-controlled — there is no second copy to fall behind.
`pfa skills install` exists for the case that cannot cover: the agent running
somewhere the repository is not.

Hermes *silently skips* an external directory that does not resolve (verified —
see [verified-facts](docs/verified-facts.md)), so `pfa doctor` reads the rendered
config and confirms the path really reaches the library, rather than trusting
that it was configured:

```console
  [PASS] skills reachable by hermes  hermes scans /srv/paul-fde-agent/skills in place (skills.external_dirs)
```

One security note that follows from the same source: external directories are
**not** a write-protection boundary. If Hermes can write there, the agent can
rewrite its own procedures — in a git working tree, quietly. The compose stack
mounts `../skills` read-only for exactly this reason.

A mistyped `--skill` is rejected before Hermes launches, with the real names
listed. The alternative is a session that quietly runs without the procedure it
was supposed to follow, which is the same failure the procedures exist to
prevent.

## 12. Lead generation

The first vertical this agent was pointed at, and the one that most needed the
rest of the project to already exist. Full guide:
[docs/lead-generation.md](docs/lead-generation.md).

It sources and enriches prospects through the lemlist MCP connector, checks each
one against the suppression list and the record-keeping rules, and writes one
personalised draft per person for review.

```bash
pfa leads init                  # create the prospect list and suppression file
pfa leads                       # the list, with each prospect's state
pfa leads check                 # compliance preflight; exits 1 if anything is blocked
pfa leads draft --limit 5       # one draft per prospect, for review
pfa leads suppress x@example.com --reason "replied stop"
```

```console
$ pfa leads check
Prospect list: private/prospects.csv
Suppression:   private/suppression.txt — 1 entries

  [   blocked] line 8: Grace Hopper (Example Systems)
               no `source` — Article 14 requires telling them where data came from
  [suppressed] line 9: Alan Turing (Example Secure)

1 ready, 0 weak, 1 blocked, 1 suppressed.
```

### Three properties, all asserted by tests

**It cannot send.** There is no send path in `src/pfa/leads.py` — not a disabled
one, not one behind a flag, not one gated on an autonomy level. The module
imports no HTTP client and no `smtplib`, and a test asserts it. This is the same
reasoning as the autonomy levels, applied harder: the reliable way to guarantee
an agent does not send email is for it to have no way to send email. You review
each draft and send it yourself.

**Prospect data does not leave the machine.** `routes.prospecting` is pinned to
the local model, which is why a prospect list has no processor to contract with
under Article 28 and no transfer to document under Article 46. This is the one
route where the provider is a compliance decision, and the cost — weaker copy
from e4b — is stated rather than hidden.

**A prospect with no provenance is refused, not warned about.** No `source` or
no `collected_at` means the Article 14 notice cannot be written, so the row
describes a person who cannot lawfully be contacted. A missing `trigger` is only
a warning: a weak message is a quality problem you may knowingly accept. The
distinction is the fact/hypothesis discipline in another form.

### What it does not do

- **Verify addresses.** That is lemlist's enrichment through the connector. The
  check in `pfa leads` is a shape check for a mangled CSV cell — a regular
  expression has never established that an address exists.
- **Decide your legal basis.** `gdpr-compliance` says what to establish and
  record, and escalates what it cannot answer. It is a procedure, not legal
  advice.
- **Track opens.** Unreliable, and itself a processing activity you would have
  to justify. Judge the targeting by replies.
- **Manage campaigns.** Sequences and sending live in lemlist, operated by a
  person.

Reasoning in full: [ADR 0007](docs/adr/0007-lead-generation.md).

## 13. Memory

Hermes provides persistent cross-session memory, FTS5 session search with LLM
summarisation, and agent-curated recall. It lives in `$HERMES_HOME`, which is a
Docker volume in the deployed stack.

**Nothing here extends it yet.** The project-scoped, inspectable, exportable
memory model — working / episodic / semantic / project — is Phase 4, and needs
the Postgres service the compose file already provisions. Today, memory is
whatever Hermes gives you.

## 14. Security

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

**Personal data:** the lead-generation vertical processes data about named
living people, so its controls are structural rather than procedural — no send
path in the code, prospect data pinned to the local model, suppression checked
before anything else and re-checked at the point of drafting, and run records
that carry no task text because a drafting prompt names someone. Details and
their limits: [docs/security.md](docs/security.md#personal-data-and-the-agent-that-touches-it).

**Prompt injection is not solved** — no honest agent project claims otherwise.
The mitigations and their limits are set out in [docs/security.md](docs/security.md).

## 15. Scheduled workflows

Hermes has a built-in cron scheduler: jobs in `~/.hermes/cron/jobs.json`, skills
attachable per job, results deliverable to multiple targets.

```bash
hermes cron create "0 8 * * *" "Prepare my morning FDE briefing" --skill fde-methodology
```

**Phase 5** adds the morning briefing, weekly AI research and prospect
monitoring workflows on top of it. The prospecting pieces those workflows need
now exist — `pfa leads check` and `pfa leads draft` are the commands a cron job
would call, and both are safe to run unattended because neither sends anything.

Prospect and client lists are configuration, never repository content:
`private/`, `prospects.*`, `suppression.txt`, `drafts/` and `clients/` are
gitignored, and tests assert they stay untracked.

## 16. Examples

```bash
# See where a task would go, and why — costs nothing
pfa route "Analyse this repository and find the documentation gaps"

# Run it (local model, free)
pfa run "Research the latest developments in MCP and what matters for a freelance FDE"

# Force the strong model regardless of phrasing
pfa run --task architecture "Should we put a queue between these two services?"

# The debugging route already attaches fde-methodology; add the API procedure
pfa run --skill api-integration "Debug this API integration"

# Prospecting: find people, then draft for them. Never sends.
pfa run "Define an ICP for companies that would buy a self-hosted GDPR-compliant agent"
pfa leads check                             # compliance preflight before anything runs
pfa leads draft --limit 5                   # one draft per prospect, for review

# See what the library holds and where each procedure attaches
pfa skills

# Validate a policy change without spending anything
pfa run --dry-run "Prepare my morning FDE briefing"

# Inspect what has been run, on which model, at what cost
pfa logs --limit 20
```

Configuration and diagnostics:

```bash
pfa config                                  # resolved policy; never prints a key
pfa mcp                                     # connectors, and which cannot authenticate
pfa doctor --json                           # machine-readable health
pfa autonomy                                # explain the four levels
pfa skills validate                         # fail the build on a malformed skill
pfa skills install                          # copy the library where the repo is absent
pfa hermes-config --autonomy read --write   # render $HERMES_HOME/config.yaml
```

## 17. Development

```
src/pfa/         config, router, skills, mcp, leads, hermes integration, runner,
                 observability, doctor, cli
config/          routing.yaml — the model policy; mcp.yaml — the connector policy
skills/          agentskills.io-format procedures (8, one per FDE work type)
docker/          Dockerfile + compose stack
docs/            architecture, security, deployment, lead-generation, verified-facts, ADRs
tests/           322 tests: config, routing, skills, mcp, leads, hermes, runner,
                 observability, security, CLI
scripts/         check-secrets.sh
private/         prospect lists, suppression, drafts — gitignored, never committed
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
sizes, the lemlist API and its MCP server — is recorded with its source and check
date in [docs/verified-facts.md](docs/verified-facts.md).

Notably: **the brief for this project specified "Hermes Agent 2.x", which does
not exist.** The project is at v0.21.0 (PyPI publishes 0.19.0). This repository
targets 0.19–0.21 and says so rather than quietly inventing a version.

## 18. Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation — structure, config, Docker, Hermes integration, local models, healthcheck, CLI | **Complete** |
| 2 | FDE skills — debugging, research, GitHub, API integration, technical writing; policy-driven attachment, validation, install | **Complete** |
| 3 | MCP connectors as validated configuration; lead generation — lemlist sourcing and enrichment, compliance preflight, draft-only outreach | **Complete** |
| 4 | Memory — persistent, project-scoped, episodic, retrieval | Next |
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

**Separate fact from hypothesis.** Every skill in the library enforces it, and
so does the code: `pfa route` reports *why* it chose a model; `pfa doctor`
reports SKIP rather than PASS for anything it cannot verify; the router's
explanation says "no rule matched" instead of implying intent. Confidently wrong
is the expensive failure mode with clients.

**Make the method automatic, not remembered.** Procedures are attached by the
routing policy, so the debugging route loads the debugging method without anyone
typing it. The day you most need the checklist is the day you are least likely to
reach for it.

**Put the constraint where it is structural.** The prospecting agent cannot
send email, because the module has no HTTP client — not because a flag is off.
The same instinct as the autonomy levels: prefer the control that cannot be
argued past to the one that merely looks like it works.

**Withdraw a plan when it stops being right.** The roadmap promised a custom MCP
server. lemlist publishes one, so building a wrapper would have added a process
to run for no capability gained. The promise is marked withdrawn rather than
quietly dropped or shipped to satisfy a plan.

**Make cost and risk visible.** Every run is logged with model, duration and
status. Every credential path is scanned before it can be pushed. Both are
things a client eventually asks about.

**Leave something maintainable.** One runtime dependency, ADRs for every real
decision, and 322 tests that run in a second without network or credentials.
The measure of an FDE engagement is what still works after you leave.

---

**License:** [MIT](LICENSE)
