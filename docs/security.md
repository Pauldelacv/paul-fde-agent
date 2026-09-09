# Security

This repository is public. Two separate concerns follow from that: keeping
secrets out of the tree, and constraining an agent that executes
model-generated commands.

## Threat model

| Threat | Control |
|---|---|
| A credential is committed and indexed forever | `.gitignore`, `make secrets-check`, four security tests in CI |
| A credential leaks through a log file shared for debugging | Redaction applied to every record before it is written |
| A credential leaks through generated config | Rendered Hermes config emits `${VAR}` references, never values |
| The agent runs a destructive command | Hermes `approvals` with an unconditional deny list; container backend |
| The agent runs unattended and approves itself | No autonomy level sets `unattended_mode` to anything but `deny` (asserted by test) |
| Prompt injection from a fetched page or a client document | Autonomy level; deny globs; container isolation. **Not fully solved — see below** |
| Client data reaches the public repo | `private/`, `var/`, `clients/`, `prospects.*` gitignored and asserted by test |

## What never enters this repository

API keys, tokens, passwords, SSH keys, `.env` files, MCP credentials, client
names or data, private conversations, prospect lists, internal hostnames, IP
addresses, production configuration.

Enforcement is layered, because a single check will eventually be bypassed:

1. **`.gitignore`** — `.env*` (with `!.env.example`), `*.db`, `*.pem`, `*.key`,
   `private/`, `var/`, `clients/`, `prospects.*`, `.hermes/`.
2. **`make secrets-check`** — scans every *tracked* file for credential
   *shapes* (`sk-…`, `ghp_…`, `xox[baprs]-…`, Telegram `NNNNNNNN:AA…`, `AKIA…`,
   PEM headers, Postgres URLs with inline passwords). Run it before every push.
3. **`tests/test_security.py`** — the same scan as a test, plus: `.env` is not
   tracked, no `.db` is tracked, `.gitignore` covers each required pattern,
   `.env.example` contains only placeholders and documents every variable the
   routing policy references, and no skill file contains a credential.
4. **Redaction at write time** — `observability.redact()` strips
   credential-shaped strings and replaces any value under a key containing
   `api_key`, `token`, `secret`, `password`, `authorization`, `credential` or
   `private_key`.

A file that must contain credential-shaped text (the redaction code, its tests,
this document) declares itself with the marker `PFA-ALLOW-SECRET-FIXTURES`.
Self-declaration is used instead of a central exclude list because a central
list silently drifts the moment someone adds a test — which it did, once,
during development, and the scanner caught it.

## Secret handling

Secrets live in exactly two places, neither tracked:

- `./.env` — for local development. `chmod 600`.
- `$HERMES_HOME/.env` — read by Hermes at load time. `chmod 600`.

The routing policy stores the *name* of the variable (`api_key_env:
PFA_CLOUD_API_KEY`), never the value. `pfa config` prints `$PFA_CLOUD_API_KEY`
and a test asserts the value never appears in its output.

If a credential is ever committed: rotate it first, then rewrite history. Rotate
first — history rewriting does not un-publish anything a crawler already fetched.

## Autonomy levels

Four levels, mapped onto Hermes' real approval controls. Set with
`pfa hermes-config --autonomy <level> --write`.

| Level | Name | Meaning | `approvals.mode` | `unattended` | `cron` |
|---|---|---|---|---|---|
| 1 | READ | Read and analyse only | `manual` | `deny` | `deny` |
| 2 | PROPOSE | Draft actions, confirm each (**default**) | `manual` | `deny` | `deny` |
| 3 | EXECUTE | Reversible actions unattended; risky patterns prompt | `smart` | `deny` | `approve` |
| 4 | EXTERNAL | External/destructive targets, explicit confirmation | `smart` | `deny` | `approve` |

Two invariants, both asserted by tests:

- **No level ever sets `unattended_mode` to anything but `deny`.** Level 4
  raises what the agent may *attempt*, never what it may do without a human.
- **No level sets `approvals.mode: off`.** Hermes supports it; this project
  does not expose it.

Always requiring explicit confirmation regardless of level: sending email,
writing to a production database, deleting files or data, deploying, financial
transactions, changing permissions, publishing content.

### Unconditional deny list

Refused before any approval mode is consulted (fnmatch globs, in
`hermes.DENY_GLOBS`):

```
*rm -rf /*          *mkfs*                  *dd if=*of=/dev/*
*chmod 777*         *DROP DATABASE*         *DROP TABLE*
*TRUNCATE TABLE*    git push --force*       git push -f*
*curl*|*sh*         *wget*|*sh*             *> /etc/*
*docker system prune*   *terraform destroy*   *kubectl delete namespace*
```

## Prompt injection — an honest limit

An agent that reads web pages, GitHub issues and client documents will
eventually read text engineered to redirect it. This project does **not** solve
that. What it does:

- keeps the default autonomy at PROPOSE, so injected instructions produce a
  confirmation prompt rather than an action;
- keeps destructive patterns on an unconditional deny list that no prompt can
  argue past;
- recommends the `docker` terminal backend, so a successful injection is
  confined to a container;
- logs the model, task and tools of every run, so an anomalous run is visible
  afterwards.

Treat any content the agent fetched as untrusted input, not as instruction.
Raising autonomy to EXECUTE or EXTERNAL on a workflow that ingests third-party
text meaningfully increases risk.

## The skill library is executable policy

Skills are the procedures the agent follows, so a skill the agent can edit is a
policy the agent can rewrite. Two facts, both verified against the Hermes skills
guide on 2026-09-02 (`verified-facts.md`):

- **`skills.external_dirs` is not a write-protection boundary.** The rendered
  Hermes config points at this repository's `skills/` directory. If the Hermes
  process can write there, the agent's `skill_manage` actions can modify the
  procedures — in a git working tree, where the change is easy to miss until
  someone reads the diff.
- **A non-existent external directory is silently skipped.** A typo in the path
  does not produce an error; it produces an agent running with no procedures at
  all, behaving plausibly and following none of them.

What this project does about it:

- The compose stack mounts `../skills:/app/skills:ro`. The read-only flag is
  load-bearing, not decoration: it is what stops the agent editing its own
  procedures on the deployed host.
- `pfa doctor` verifies the configured path actually resolves to the library,
  rather than trusting that it was configured.
- `pfa skills validate` runs in `make check`, so a malformed procedure fails the
  build rather than being quietly ignored at load time.
- A test asserts no skill contains a credential, an absolute home directory or a
  non-example hostname — skills are committed to a public repository, and client
  detail leaking into one is a disclosure, not an untidiness.

Running the agent as a user that cannot write to the checkout is the stronger
form of the first control, and is what a deployment outside Docker should do.

## Personal data, and the agent that touches it

The lead-generation vertical is the first part of this project that processes
data about **named living people**. That changes the threat model: the worst
outcome is no longer a wasted token or a broken repository, it is a message to
someone who asked never to be contacted again.

Three controls, in decreasing order of how much they are worth:

**There is no send path.** `src/pfa/leads.py` imports no HTTP client, no
`smtplib`, nothing that can reach the network. It writes files. A test asserts
the module names no transport and exposes no function beginning with `send`.
This is deliberately stronger than an approval gate: ADR 0003 established that a
permission check outside the agent loop cannot block a call, and the same logic
applies here — the reliable way to guarantee an agent does not send email is for
it to have no way to send email.

**Prospect data does not leave the machine.** `routes.prospecting` is pinned to
the local model. This is a compliance control, not a cost one: a list that never
reaches a hosted model has no processor to contract with under Article 28 and no
transfer to document under Article 46. `config/routing.yaml` says so at the line
someone would edit.

**Suppression is checked before anything else.** Before enrichment, before
drafting, before a prospect is even listed — and re-checked inside `draft_for`,
because that function is importable and its guarantee has to hold for a caller
that skipped the preflight. The list is appended to, never rewritten, so a
partial write cannot lose an entry.

Alongside those, the ordinary hygiene:

- Everything lives under `$PFA_PRIVATE_DIR` (`private/`, or `/data/private` in
  Docker), gitignored, with tests asserting nothing under it is tracked.
- Run records carry the task category, model, duration and status — **never the
  task text**. A drafting prompt contains a named person's details, and
  `pfa logs` output is the natural thing to paste into a support thread. A test
  asserts the record has no text field.
- A row with no `source` or `collected_at` is refused rather than warned about:
  Article 14 requires telling someone where their data came from, so a row
  without it describes a person who cannot lawfully be contacted.

### What these controls do not cover

- **A volume backup contains the prospect list.** `agent-data` holds
  `/data/private`. Encrypt it, and apply the same retention you promised in the
  Article 14 notice — a backup is a copy, and deleting the original does not
  delete it.
- **The lemlist connector's tool exclusions are focus, not security.** lemlist
  documents that narrowing the advertised tool set does not restrict access,
  because a generic `call_api` tool remains available in every bucket. The real
  boundary is the scope of the API key itself.
- **The code cannot check the truth of a source, only its presence.** Nor
  whether your balancing test is sound, nor whether the national marketing rules
  were read. The `gdpr-compliance` skill states it is a procedure and not legal
  advice, and escalates what it cannot answer.
- **A rights request must reach a human.** The agent's job is to recognise one —
  including "stop emailing me" in a reply — and escalate it, never to answer it.

## MCP connectors are network reach

Every connector in `config/mcp.yaml` is a route out of the container and a set
of tools the model can call. Two things follow.

**A missing credential fails misleadingly.** Hermes keeps an unset `${VAR}`
verbatim and only logs a warning (verified 2026-09-09), so a connector with no
key connects and sends the literal placeholder text as its credential. The 401
that comes back reads like a revoked key. `pfa doctor` and `pfa mcp` report it
before a connection is attempted, and the loader refuses a server that
references a variable it has not declared in `requires_env`.

**The rendered config holds references, never values.** `${VAR}` survives into
`$HERMES_HOME/config.yaml` and Hermes resolves it at connect time, so the file
stays safe to read, diff and back up. A test sets a real-looking key in the
environment and asserts it does not appear in the rendered document.

Scope every connector's credential at the provider. A tool filter shapes what
the model is offered; only the key decides what the account can do.

## Deployment hardening

- Run the container as non-root (the image does; UID 10001).
- Use the `docker` terminal backend so command execution is contained.
- Do not publish the Ollama port; the compose file only `expose`s it.
- `no-new-privileges:true` is set on the agent service.
- Never set `GATEWAY_ALLOW_ALL_USERS=true` if you enable a chat gateway.
- Back up `$HERMES_HOME` — and treat the backup as secret-bearing, because it
  contains `.env` and the session database.

## Reporting

Found a vulnerability? Open an issue for anything non-sensitive. For anything
exploitable, contact the maintainer directly rather than filing publicly.
