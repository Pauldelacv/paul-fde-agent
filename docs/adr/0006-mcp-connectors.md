# ADR 0006 — Declare MCP connectors in configuration, and connect to hosted servers rather than writing them

**Status:** Accepted · **Date:** 2026-09-09

## Problem

Phase 3 is "MCP", and the README has said since Phase 1 that it would ship
"one minimal custom server built to demonstrate the protocol end to end". Two
things had to be settled before writing any of it.

**What actually needs building?** Hermes is MCP-native. It has the client, the
transports, tool discovery, per-server filtering and OAuth. A connector is a
handful of YAML keys. The honest question is the same one Phase 1 asked about
the agent loop: what is left for us once the runtime's own capability is
subtracted?

**What happens when a connector is misconfigured?** This turned out to be the
part with teeth. Re-reading the Hermes configuration reference on 2026-09-09
(recorded in `verified-facts.md`) turned up a documented behaviour with an
unpleasant failure shape: **an unset `${VAR}` is kept verbatim and only logged
as a warning.** A connector whose API key is missing therefore does not fail to
start. It connects, sends the literal nine-character-plus string
`${LEMLIST_API_KEY}` as its credential, and gets a 401 — which reads exactly
like a revoked key and sends whoever is debugging it to regenerate a key that
was never the problem.

## Options

1. **Write a custom MCP server for lead generation.** It demonstrates the
   protocol, which is what the original plan said. It also means owning a
   server that wraps an API whose vendor already publishes one.
2. **Document the config and let the operator write it by hand.** Zero code.
   Also zero validation, and the `${VAR}` failure above stays live.
3. **Declare connectors in `config/mcp.yaml`, validate them, and render them
   into the Hermes config** — the same shape `config/routing.yaml` already has
   for models and skills.

## Decision

Option 3, and **no custom server**.

lemlist publishes a hosted MCP server (verified 2026-09-09). Connecting to it
is a URL and a header. Writing our own to sit in front of it would add a
process to run, a protocol implementation to keep current, and a second place
for the tool list to be wrong — in exchange for nothing the hosted server does
not already do. ADR 0004's rule about dependencies applies to components too:
it has to earn its place, and this one cannot.

So the README's promise of a custom server is **withdrawn rather than
deferred**, and the roadmap says so. Shipping one now would have been building
to a plan instead of to a need.

### What `config/mcp.yaml` adds over hand-written YAML

- **Validation with a remedy.** Transport-appropriate keys, string headers,
  well-formed names.
- **A declared-credentials rule.** Every `${VAR}` a server references must
  appear in its `requires_env`. This is the direct answer to the verbatim
  passthrough: an undeclared reference is one no check covers, so the loader
  refuses it. Both spellings Hermes accepts — `${VAR}` and `${env:VAR}` — are
  recognised, so neither evades the rule.
- **A pre-flight report.** `pfa mcp` and `pfa doctor` both say which connectors
  cannot authenticate, naming the variable, *before* a connection is attempted.
- **A place to write down what is deliberately absent**, which is half of what
  the file is for. See the comment block at its foot.

### The reference is not expanded, and that is the point

`config/routing.yaml` is expanded at load time because we act on its values.
`config/mcp.yaml` is the opposite: the `${VAR}` must survive into
`$HERMES_HOME/config.yaml` so Hermes resolves it at connect time. Expanding it
here would write the credential into a file that gets read while debugging and
copied into backups. A test asserts a real-looking key set in the environment
does not appear in the rendered document.

### Tool exclusions are focus, not security

`config/mcp.yaml` excludes lemlist's send, launch and delete tools. This is
stated in the file as a posture rather than a control, because lemlist's own
documentation says plainly that narrowing the advertised tool set does not
restrict access — a generic `call_api` tool remains available in every bucket.
The real restriction is scoping the API key in lemlist, which
`docs/lead-generation.md` tells the operator to do. Describing the exclusions
as a security boundary would be the sort of claim this project exists not to
make.

## Trade-offs accepted

- **A connector we do not host can change under us.** lemlist can add, rename
  or remove tools without notice, and our exclusion globs are matched against
  names we do not control. `pfa doctor` cannot detect that; only a failing run
  will. Accepted, because the alternative is maintaining a wrapper that would
  break in the same way with more code.
- **`enabled: true` by default for lemlist.** A connector nobody enabled is a
  connector nobody uses, so the shipped file enables it and `pfa doctor` warns
  loudly until the key exists. The cost is one warning on a fresh clone; the
  alternative cost is a feature that silently does nothing.
- **We validate what Hermes will validate again.** Same reasoning as ADR 0005:
  the failure we care about is the one where Hermes proceeds with a bad value
  rather than rejecting it, and a check that only runs inside the runtime
  cannot report on a repository.
- **No Postgres connector**, though the compose stack provisions Postgres. The
  memory layer that will write to it does not exist yet, and a connector to an
  empty database is surface area with no user. It arrives with Phase 4.
- **No GitHub connector.** Hermes' own documentation says GitHub is excluded
  from its catalogue deliberately, because its bundled `github/*` skills
  driving the `gh` CLI are the better integration. Adding one would be a worse
  copy of something the runtime already does — the same conclusion Phase 1
  reached about the agent loop.
