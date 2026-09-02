# Paul FDE Agent — common operations.
# `make help` lists everything.

SHELL := /bin/bash
COMPOSE := docker compose -f docker/docker-compose.yml
PY := python3

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- local development -----------------------------------------------------

.PHONY: install
install: ## Install the package with dev extras into the current environment
	$(PY) -m pip install -e '.[dev]'

.PHONY: install-hermes
install-hermes: ## Also install the Hermes runtime (large dependency tree)
	$(PY) -m pip install -e '.[hermes,dev]'

.PHONY: test
test: ## Run the full test suite
	$(PY) -m pytest

.PHONY: lint
lint: ## Lint and format-check
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

.PHONY: fmt
fmt: ## Auto-format
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

.PHONY: doctor
doctor: ## Check the environment
	$(PY) -m pfa.cli doctor

.PHONY: skills
skills: ## List the FDE skill library and where each procedure attaches
	$(PY) -m pfa.cli skills

.PHONY: skills-validate
skills-validate: ## Fail if any skill is malformed
	$(PY) -m pfa.cli skills validate

.PHONY: skills-install
skills-install: ## Copy the skill library into $$HERMES_HOME/skills
	$(PY) -m pfa.cli skills install

.PHONY: check
check: lint test skills-validate ## Everything CI runs

# --- secrets safety --------------------------------------------------------

.PHONY: secrets-check
secrets-check: ## Fail if anything credential-shaped is staged or tracked
	@scripts/check-secrets.sh

# --- deployment ------------------------------------------------------------

.PHONY: up
up: ## Start the self-hosted stack
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack (volumes are preserved)
	$(COMPOSE) down

.PHONY: logs
logs: ## Follow container logs
	$(COMPOSE) logs -f --tail=100

.PHONY: ps
ps: ## Show stack status and health
	$(COMPOSE) ps

.PHONY: shell
shell: ## Open a shell inside the agent container
	$(COMPOSE) exec agent bash

.PHONY: pull-models
pull-models: ## Pull the local Gemma 4 models the routing policy references
	$(COMPOSE) exec ollama ollama pull gemma4:e2b
	$(COMPOSE) exec ollama ollama pull gemma4:e4b

.PHONY: hermes-config
hermes-config: ## Render $HERMES_HOME/config.yaml from the routing policy
	$(PY) -m pfa.cli hermes-config --write
