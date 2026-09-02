# ---------------------------------------------------------------------------
# Paul FDE Agent — runtime image
#
# Base: python:3.11-slim. Hermes declares requires_python >=3.11,<3.14, and
# 3.11 is the version its own installer bundles on Windows, so it is the
# best-supported target rather than merely the newest.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

# System packages:
#   ripgrep      — Hermes uses it for code/session search; documented dependency.
#   git          — the GitHub skills operate on real clones.
#   nodejs/npm   — stdio MCP servers are commonly `npx @modelcontextprotocol/...`.
#   curl         — container healthcheck and Ollama probing.
# Deliberately omitted: ffmpeg. It is only needed for Hermes' audio features,
# which this project does not use, and it costs ~250MB. Add it if you enable
# voice.
RUN apt-get update && apt-get install --no-install-recommends -y \
        ripgrep \
        git \
        curl \
        ca-certificates \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user. The agent executes model-generated commands; the
# container is a security boundary and root inside it weakens that boundary.
ARG UID=10001
RUN useradd --create-home --uid ${UID} --shell /bin/bash agent

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HERMES_HOME=/data/hermes \
    PFA_LOG_DIR=/data/logs \
    PFA_CONFIG=/app/config/routing.yaml \
    PFA_SKILLS_DIR=/app/skills

WORKDIR /app

# Dependency layer first so source edits do not invalidate the install cache.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir '.[hermes]'

COPY config/ ./config/
COPY skills/ ./skills/
COPY scripts/ ./scripts/

# Persistent state lives on a volume, never in the image layer.
RUN mkdir -p /data/hermes /data/logs && chown -R agent:agent /data /app
USER agent
VOLUME ["/data"]

# The healthcheck is `pfa doctor`, the same command an operator runs by hand.
# It exits 0 on PASS, 1 on WARN, 2 on FAIL; we accept WARN because a missing
# optional cloud key should not mark the container unhealthy.
HEALTHCHECK --interval=60s --timeout=20s --start-period=30s --retries=3 \
    CMD pfa doctor --json > /dev/null 2>&1 || [ $? -le 1 ]

ENTRYPOINT ["pfa"]
CMD ["doctor"]
