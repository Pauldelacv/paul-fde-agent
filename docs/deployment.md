# Deployment

## Local development

```bash
git clone https://github.com/pauldelacv/paul-fde-agent.git
cd paul-fde-agent
python3 -m venv .venv && source .venv/bin/activate
make install-hermes          # or `make install` to skip the Hermes runtime
cp .env.example .env && chmod 600 .env
$EDITOR .env
pfa doctor
```

`pfa doctor` exits 0 (PASS), 1 (WARN) or 2 (FAIL) and prints a remedy for every
non-passing check.

## VPS deployment

Requirements: Linux, Docker with the Compose plugin, **12 GB RAM** and ~15 GB
free disk (the two models are ~17 GB together; drop `gemma4:e2b` from
`make pull-models` if disk is tight). See [Sizing](#sizing).

```bash
git clone https://github.com/pauldelacv/paul-fde-agent.git
cd paul-fde-agent
cp .env.example .env && chmod 600 .env
$EDITOR .env                 # POSTGRES_PASSWORD is mandatory — compose fails without it
make deploy
```

`make deploy` builds the image, starts the stack, pulls both models, renders
`$HERMES_HOME/config.yaml`, and finishes by running `make smoke`. Expect the
first run to take a while: the image installs the Hermes dependency tree, and
the models are a large download.

### What `make smoke` proves

It runs five checks against the deployed stack and spends nothing:

```bash
make smoke
```

| Check | What a pass means |
|---|---|
| `pfa doctor` | Policy loads, Hermes is installed, Ollama answers, skills are reachable |
| `pfa mcp` | Every enabled connector has its credential — see the 401 note below |
| `pfa route` | Classification and model selection work |
| `pfa skills validate` | All eight procedures parse |
| `pfa run --dry-run` | The whole path runs without invoking a model |

`pfa doctor` exits 0 (PASS), 1 (WARN) or 2 (FAIL) and prints a remedy for every
non-passing check. A WARN for `provider:cloud credentials` is expected if you
are running local-only.

Then run a real task:

```bash
docker compose -f docker/docker-compose.yml exec agent \
  pfa run "Research the latest developments in MCP and what matters for a freelance FDE"
```

### MCP connectors

```bash
docker compose -f docker/docker-compose.yml exec agent pfa mcp
```

`NEEDS $LEMLIST_API_KEY` is worth acting on rather than ignoring. Hermes keeps an
unset `${VAR}` verbatim and only logs a warning, so a connector with no key does
not fail to start — it authenticates with the literal string
`${LEMLIST_API_KEY}` and gets a **401**, which looks like a revoked key and sends
you to regenerate one that was never the problem. Set the key in `.env` and
`make up` again, or set `enabled: false` for that server in `config/mcp.yaml`.

### Lead generation

Setup, the prospect list format and the daily commands are in
[lead-generation.md](lead-generation.md). The short version:

```bash
make leads-init              # create the prospect list inside the container
make leads-pull              # copy it out to ./private to edit
$EDITOR private/prospects.csv
make leads-push              # copy back in, and run the compliance preflight
make leads-draft             # draft for every ready prospect — sends nothing
make leads-pull              # bring the drafts back out to read
```

`./private` holds personal data. It is gitignored, and so is any copy of it.

## Sizing

Read this before choosing a VPS. A small CPU box will **not** run every Gemma 4
variant usefully. Approximate requirements at Q4_K_M, CPU-only:

| Variant | Download | RAM needed | Usable on a small CPU VPS? |
|---|---|---|---|
| `gemma4:e2b` | ~7.2 GB | ~6 GB | Yes |
| `gemma4:e4b` | ~9.6 GB | ~10 GB | Yes, if the box has ≥12 GB |
| `gemma4:26b` (MoE, 3.8B active) | ~18 GB | ~20 GB | Only on a large instance |
| `gemma4:31b` (dense) | ~20 GB | ~24 GB | Realistically GPU only |

**The shipped policy uses `e4b` for every local route**, including `debugging`
and `prospecting`, so it runs on the machine this project is built to be
deployed on. That is a deliberate change from an earlier version that routed
`debugging` to `26b` — a better model for a stack trace, and one that will not
run usefully on a CPU VPS.

If your host can carry more, raise it:

```yaml
# config/routing.yaml
routes:
  debugging:
    provider: local
    model: "gemma4:26b"    # needs ~20 GB RAM; add it to `make pull-models` too
```

Or send it to the cloud provider instead:

```yaml
  debugging:
    provider: cloud
    model: null
```

Verify what you changed before spending anything:

```bash
pfa route "debug this failing integration"
```

**One route should not be moved to the cloud without thinking about it.**
`prospecting` handles personal data, and it is local so that a prospect list has
no processor to contract with and no transfer to document. Changing it is a
compliance decision — see [ADR 0007](adr/0007-lead-generation.md).

## GPU

The compose file is CPU-only, because that is the honest default for a cheap
VPS. For a GPU host, add to the `ollama` service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

This requires the NVIDIA Container Toolkit on the host.

## Persistence and backups

Three named volumes hold all state: `ollama-models` (re-downloadable),
`postgres-data`, and `agent-data` (`$HERMES_HOME` — config, memory, sessions,
logs — **and `/data/private`, which holds prospect lists, the suppression list
and generated drafts**).

```bash
docker run --rm -v paul-fde-agent_agent-data:/data -v "$PWD":/backup \
  alpine tar czf /backup/agent-data-$(date +%F).tar.gz -C /data .
```

**The backup contains `$HERMES_HOME/.env`, the session database and every
prospect's personal data.** Treat it as secret-bearing: encrypt it, never commit
it, and apply the same retention period you promised in your Article 14 notice —
a backup is a copy, and deleting the original does not delete it.

The suppression list is inside that volume too, and it is the one record you
cannot afford to lose: restoring a backup taken before someone objected will
re-contact them. Keep a separate copy of `/data/private/suppression.txt`.

## Health and recovery

The image's `HEALTHCHECK` runs `pfa doctor`, accepting PASS and WARN. Postgres
uses `pg_isready`; Ollama uses `ollama list`. The agent service waits for both
to be healthy before starting.

| Symptom | Likely cause | Action |
|---|---|---|
| `provider:local endpoint` WARN | Ollama not up | `make ps`, then `make logs` |
| Model not found at run time | Model never pulled | `make pull-models` |
| `hermes runtime` FAIL | Installed without the extra | `pip install -e '.[hermes]'` |
| Compose refuses to start | `POSTGRES_PASSWORD` unset | Set it in `.env` — this failure is deliberate |
| Runs are very slow | Model too large for the host | See the sizing table above |
| `mcp:<name> credentials` WARN | Connector key unset | Set it in `.env`, or `enabled: false` in `config/mcp.yaml` |
| A connector returns 401 with a key that works elsewhere | The `${VAR}` never resolved | `pfa mcp` — Hermes passes an unset one through verbatim |
| `pfa leads` says "No prospect list" | Never initialised | `make leads-init` |
| A prospect is `blocked` | No `source` or `collected_at` | Fill both in; Article 14 needs the source |
| Drafts are not on the host | They are on the volume | `make leads-pull` |

Full reset, preserving data:

```bash
make down && make up
```

Destroying volumes (**irreversible**):

```bash
docker compose -f docker/docker-compose.yml down -v
```

## Upgrading Hermes

Hermes is 0.x and ships releases every few days; treat every upgrade as a
potentially breaking change.

```bash
pip install -U 'hermes-agent<0.22.0'
pfa doctor                   # confirms the resolved version
make test
```

If a flag we pass has changed, `docs/verified-facts.md` lists every one of them
with its source — start there.
