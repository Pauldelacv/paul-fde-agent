# Verified facts

Every external claim this project makes is recorded here with its source and the
date it was checked. If a statement about Hermes or Gemma is not in this file,
it has not been verified and should not be relied on.

Last verified: **2026-09-01**; skills rows re-checked **2026-09-02**.

## Hermes Agent

| Claim | Status | Source |
|---|---|---|
| Built by Nous Research; MIT licensed | Verified | [Official docs](https://hermes-agent.nousresearch.com/docs/) |
| **There is no version 2.x** | Verified | [Releases](https://github.com/NousResearch/hermes-agent/releases) |
| Latest GitHub release is `v0.21.0` (tag `v2026.8.31`, 2026-08-31) | Verified | [Releases](https://github.com/NousResearch/hermes-agent/releases) |
| Latest PyPI release is `0.19.0`; PyPI lags GitHub | Verified | [PyPI JSON API](https://pypi.org/pypi/hermes-agent/json) |
| `requires_python >=3.11,<3.14` | Verified | PyPI metadata |
| Config lives at `$HERMES_HOME/config.yaml`, default `~/.hermes` | Verified | [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Secrets in `$HERMES_HOME/.env`; `${VAR}` substitution in YAML | Verified | Configuration docs |
| Custom OpenAI-compatible providers via `providers.<name>.base_url` | Verified | Configuration docs |
| Model reference format is `provider/model` | Verified | Configuration docs |
| `auxiliary` routes side-tasks (compression, vision, title generation) | Verified | Configuration docs |
| **No built-in routing by user-task category** | Verified (absence) | Configuration docs — `auxiliary` covers internal side-tasks only |
| MCP servers under `mcp_servers` key; stdio, HTTP, OAuth 2.1 transports | Verified | [MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) |
| Skills at `$HERMES_HOME/skills/<category>/<name>/SKILL.md`, agentskills.io format | Verified | [Skills guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) |
| Skill frontmatter is YAML between `---` fences (`name`, `description`, `version`, optional `platforms`, `metadata.hermes.tags`), followed by Markdown | Verified 2026-09-02 | Skills guide — "SKILL.md Format" |
| `skills.external_dirs` in `config.yaml` makes Hermes scan additional skill directories in place; `~` and `${VAR}` expand | Verified 2026-09-02 | Skills guide — "External Skill Directories" |
| A configured external skill dir that does not exist is **silently skipped**, not reported | Verified 2026-09-02 | Skills guide — "Non-existent paths are silently skipped" |
| A local skill shadows an external one of the same name | Verified 2026-09-02 | Skills guide — "Local precedence" |
| External dirs are **not** a write-protection boundary: the agent can modify skills there if the process can write to them | Verified 2026-09-02 | Skills guide — "External dirs are not a write-protection boundary" |
| Built-in cron; jobs in `~/.hermes/cron/jobs.json`; skills attachable to jobs | Verified | [Cron guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) |
| `approvals` block: `mode` (`smart`/`manual`/`off`), `cron_mode`, `unattended_mode`, `deny` globs | Verified | [Security guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md) |
| Terminal backends: local, docker, ssh, daytona, singularity, modal, vercel_sandbox | Verified | Security guide |
| CLI flags `-q/--query`, `--oneshot`, `-Q/--quiet`, `-m/--model`, `-s/--skills` | Verified | [CLI reference](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/cli-commands.md) |
| `HERMES_HOME` env var overrides the config directory | Verified | CLI reference |

### What this means for us

The version number in the original project brief (“Hermes Agent 2.x”) does not
exist. This project targets **0.19.x – 0.21.x** and pins that range in
`pyproject.toml`. Because 0.x software makes no backwards-compatibility promise,
`pfa doctor` reports the *resolved* version at runtime rather than trusting the
pin, and every Hermes flag we pass is listed above with its source.

The skills rows are what Phase 2 is built on. Two of them changed the design
rather than merely documenting it: `external_dirs` means the repository's
`skills/` directory can be scanned in place, so `pfa hermes-config --write` now
points Hermes at it instead of relying on a copy that can fall behind — and
because a non-existent external dir is *silently skipped*, `pfa doctor` verifies
that the configured path actually resolves to the library rather than trusting
that it was configured.

## Gemma 4

| Claim | Status | Source |
|---|---|---|
| Released 2026-04-02 by Google DeepMind, Apache 2.0 | Verified | [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) |
| Sizes: E2B, E4B, 26B MoE (3.8B active), 31B dense; 12B unified multimodal added June 2026 | Verified | Google blog |
| Day-one Ollama support: `ollama pull gemma4:e2b` etc., Q4_K_M default | Verified | Ollama / vendor guides |
| Native function calling — required for agentic tool use | Verified | Google blog |
| 128K–256K context window | Verified | Google blog |

### What this means for us

Function calling is the load-bearing capability: an agent runtime without it
cannot use tools, so Gemma 4 is a viable local backend in a way that many small
open models are not. Size is the constraint, not capability — see
[deployment.md](deployment.md) for what actually fits on a small CPU VPS.

## Re-verifying

These facts decay. Before trusting this file after a few months, re-check the
two release pages and update the dates:

```bash
curl -s https://pypi.org/pypi/hermes-agent/json | jq -r '.info.version, .info.requires_python'
```
