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

Requirements: Linux, Docker with the Compose plugin, ~10 GB disk for the E4B
model, and RAM per the sizing table below.

```bash
git clone https://github.com/pauldelacv/paul-fde-agent.git
cd paul-fde-agent
cp .env.example .env && chmod 600 .env
$EDITOR .env                 # POSTGRES_PASSWORD is mandatory — compose fails without it
make up
make pull-models             # downloads gemma4:e2b and gemma4:e4b
make ps                      # all services should report healthy
docker compose -f docker/docker-compose.yml exec agent pfa doctor
```

Then run a task:

```bash
docker compose -f docker/docker-compose.yml exec agent \
  pfa run "Research the latest developments in MCP and what matters for a freelance FDE"
```

## Sizing — read this before choosing a VPS

A small CPU VPS will **not** run every Gemma 4 variant usefully. Approximate
requirements at Q4_K_M, CPU-only:

| Variant | Download | RAM needed | Usable on a small CPU VPS? |
|---|---|---|---|
| `gemma4:e2b` | ~7.2 GB | ~6 GB | Yes |
| `gemma4:e4b` | ~9.6 GB | ~10 GB | Yes, if the box has ≥12 GB |
| `gemma4:26b` (MoE, 3.8B active) | ~18 GB | ~20 GB | Only on a large instance |
| `gemma4:31b` (dense) | ~20 GB | ~24 GB | Realistically GPU only |

The shipped policy routes `debugging` to `gemma4:26b`. **On a small VPS this
will be unusably slow.** Either change that route to `e4b`, or point it at the
cloud provider:

```yaml
# config/routing.yaml
routes:
  debugging:
    provider: cloud      # was: local / gemma4:26b
    model: null
```

Verify what you changed before spending anything:

```bash
pfa route "debug this failing integration"
```

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
`postgres-data`, and `agent-data` (`$HERMES_HOME` — config, skills, memory,
sessions, logs).

```bash
docker run --rm -v paul-fde-agent_agent-data:/data -v "$PWD":/backup \
  alpine tar czf /backup/agent-data-$(date +%F).tar.gz -C /data .
```

**The backup contains `$HERMES_HOME/.env` and the session database.** Treat it
as secret-bearing: encrypt it, and never commit it.

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
