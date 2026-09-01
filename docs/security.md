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
