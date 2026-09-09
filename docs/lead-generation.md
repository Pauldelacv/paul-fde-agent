# Lead generation

The agent finds and researches prospects, and writes one outreach message per
prospect for you to review. **It never sends anything.** There is no send path
in the code — see [ADR 0007](adr/0007-lead-generation.md).

Everything here handles personal data. Read [Before you start](#before-you-start)
before the commands.

---

## What it does, end to end

```
  config/mcp.yaml            private/prospects.csv        private/suppression.txt
  (lemlist connector)        (who, and where from)        (who asked you to stop)
        │                            │                            │
        ▼                            ▼                            ▼
  hermes + lemlist MCP  ──►   pfa leads check   ──────────────────┘
  source · enrich · verify    provenance + suppression preflight
        │                            │
        └──────────────┬─────────────┘
                       ▼
                pfa leads draft
        local gemma4:e4b + lead-generation
        + gdpr-compliance + outreach-writing
                       │
                       ▼
        private/drafts/<date>/<prospect>.md
              "awaiting human review. Not sent."
                       │
                       ▼
              YOU read, edit, and send
```

Two halves, and it is worth being clear about which is which. **Sourcing and
enrichment** happen through the lemlist MCP connector, inside a Hermes session
— lemlist hosts that server, so it is configuration, not code we wrote.
**Listing, compliance preflight and drafting** are `pfa leads`, which is code in
this repository and runs with no network access of its own.

## Before you start

Three things are true of this vertical and not of the rest of the project:

1. **A prospect list is personal data.** Including work addresses. It lives in
   `private/` (or `/data/private` in Docker), which is gitignored, and tests
   assert it stays untracked.
2. **The prospecting route runs on the local model on purpose.** Prospect data
   is not sent to a hosted model, so there is no processor to contract with and
   no transfer to document. Changing that route is a compliance decision —
   `config/routing.yaml` says so at the line you would edit.
3. **The agent drafts; you send.** Review each draft. This is the control that
   makes the rest safe.

The `gdpr-compliance` skill is a procedure, not legal advice. It tells you what
to establish and record; it does not decide whether your basis is sound.

## Setup

### 1. Get a lemlist API key

In lemlist: **Settings → Team → Integrations → Generate**. It is shown once.

**Scope it as narrowly as lemlist allows.** The connector excludes lemlist's
send, launch and delete tools, but lemlist documents plainly that narrowing the
advertised tool set is *not* access control — a generic `call_api` tool remains
available. The key's own scope is the real boundary.

```bash
echo 'LEMLIST_API_KEY=<your key>' >> .env
chmod 600 .env
```

### 2. Check the connector

```bash
pfa mcp
```

```console
MCP connectors: config/mcp.yaml

  lemlist     http   ready
              https://app.lemlist.com/mcp?bucket=prospecting
              Prospect sourcing, email enrichment and campaign leads. …
```

`NEEDS $LEMLIST_API_KEY` instead of `ready` matters more than it looks. Hermes
keeps an unset `${VAR}` verbatim and only logs a warning, so a connector with no
key does not fail to start — it authenticates with the literal text
`${LEMLIST_API_KEY}` and comes back **401**, which reads like a revoked key.
`pfa mcp` and `pfa doctor` catch it first.

### 3. Point Hermes at it

```bash
pfa hermes-config --write
pfa doctor
```

The rendered `$HERMES_HOME/config.yaml` contains `${LEMLIST_API_KEY}`, never the
key itself — Hermes resolves it at connect time. The file stays safe to read,
diff and back up.

### 4. Create the prospect list

```bash
pfa leads init
```

Creates `private/prospects.csv` and `private/suppression.txt`. It refuses to
overwrite either: the suppression list is the one file whose loss re-contacts
people who objected.

## The prospect list

| Column | Required | What it is for |
|---|---|---|
| `email` | yes | The address. Verified through lemlist, not by this tool. |
| `first_name`, `last_name` | — | Addressing them. Missing is a warning. |
| `role`, `company` | — | Context for the message. |
| `source` | **yes** | Where the data came from, *by name*. Article 14 requires telling them. |
| `collected_at` | **yes** | `YYYY-MM-DD`. Retention cannot be enforced without it. |
| `trigger` | — | Why now. Missing is a warning: the message will be generic. |
| `trigger_source` | — | What makes the trigger checkable. |
| `notes` | — | Anything else. |

Lines beginning with `#` are ignored, so the file can carry a banner saying what
it holds.

**`source` and `collected_at` are hard gates.** A row without them is refused,
not warned about: Article 14 obliges you to say where someone's data came from,
so a row with no source describes a person who cannot lawfully be contacted.
A missing `trigger` is only a warning — a weak message is a quality problem you
may knowingly accept.

## Daily use

```bash
pfa leads                       # the list, with each prospect's state
pfa leads check                 # compliance preflight; exits 1 if anything is blocked
pfa leads draft --dry-run       # show the prompts; invoke no model, write nothing
pfa leads draft --limit 5       # draft for five prospects
pfa leads suppress someone@example.com --reason "replied stop"
```

### `pfa leads check`

```console
Prospect list: private/prospects.csv
Suppression:   private/suppression.txt — 1 entries

  [   blocked] line 8: Grace Hopper (Example Systems)
               no `source` — Article 14 requires telling them where data came from
  [suppressed] line 9: Alan Turing (Example Secure)

1 ready, 0 weak, 1 blocked, 1 suppressed.
```

Four states: **ready** (complete), **weak** (draftable, no trigger recorded),
**blocked** (cannot be drafted for), **suppressed** (asked not to be contacted).

### `pfa leads draft`

Runs the agent once per prospect and writes
`private/drafts/<date>/<prospect>.md`. Every draft carries its provenance, the
model that wrote it, and the line **"awaiting human review. Not sent."**

Blocked and suppressed prospects are skipped with the reason on stderr.
`--dry-run` prints the prompt and writes nothing — useful for checking the whole
pipeline before any model is installed.

### Objections

```bash
pfa leads suppress someone@example.com --reason "replied stop"
```

Immediate and permanent. Checked before enrichment, before drafting, before a
prospect is listed — every run, not every campaign. A soft "not right now" is an
objection too.

## On the VPS

Prospect data lives on the `agent-data` volume, not a bind mount: the container
runs as uid 10001 and a host directory owned by anyone else is unwritable in a
way Docker only reports at the first write.

```bash
make leads-init                 # create the files inside the container
make leads-pull                 # copy them out to ./private to edit
$EDITOR private/prospects.csv
make leads-push                 # copy back in, then run the preflight
make leads-draft                # draft for every ready prospect
make leads-pull                 # bring the drafts back out to read
```

`./private` is gitignored. It still holds real people's data — treat the
directory, and any backup of the volume, as secret-bearing.

If you would rather edit in place, bind-mount it and fix the ownership once:

```yaml
# docker/docker-compose.yml, agent service
    volumes:
      - ../private:/data/private
```

```bash
sudo chown -R 10001:10001 private
```

## Asking the agent directly

Not everything is a list operation. The `prospecting` route classifies these
automatically and attaches the procedures:

```bash
pfa run "Define an ICP for companies that would buy a self-hosted GDPR-compliant AI agent"
pfa run "Search lemlist for CTOs at French SaaS companies of 50-200 people hiring a DPO"
pfa run "Review these enrichment results and tell me which addresses are actually usable"
pfa route "draft a cold email sequence"     # see the decision before spending anything
```

`pfa route` shows the model and the attached procedures before a token is spent.

## What this does not do

Stated plainly, because each is a thing someone will reasonably expect:

- **It does not send.** Ever. By construction, not by configuration.
- **It does not verify addresses.** That is lemlist's enrichment through the
  connector. The check in `pfa leads` is a shape check for a mangled CSV cell —
  a regular expression has never established that an address exists.
- **It does not decide your legal basis.** `gdpr-compliance` tells you what to
  establish and record, and escalates what it cannot answer.
- **It does not track opens or replies.** Open tracking is unreliable and is
  itself a processing activity you would have to justify. Judge the targeting by
  replies.
- **It does not manage campaigns.** Sequences, scheduling and sending live in
  lemlist, where a person operates them.

## Reference

- [ADR 0007](adr/0007-lead-generation.md) — why local, why draft-only, why
  provenance is a hard gate
- [ADR 0006](adr/0006-mcp-connectors.md) — why the connector is configuration
  and not a custom server
- [verified-facts](verified-facts.md#lemlist) — the lemlist API and MCP facts,
  with sources and dates
- [security](security.md) — personal data handling and the limits of the
  guarantees above
