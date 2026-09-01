# ADR 0001 — Build on Hermes rather than on a general agent framework

**Status:** Accepted · **Date:** 2026-09-01

## Problem

The project needs an agent runtime: an agent loop, tool calling, MCP support,
memory, scheduling and an approval mechanism. Building that is 6–12 months of
work and is not the point of the project.

## Options

1. **LangGraph / CrewAI / a similar orchestration library.** Mature, widely
   used. But they are *libraries*: MCP, persistent memory, cron, approvals and
   sandboxed execution are all still ours to assemble and maintain.
2. **Write a minimal loop directly against a model API.** Maximum control,
   maximum understanding. Also the slowest path to something useful, and the
   result is a worse version of what already exists.
3. **Hermes Agent as the runtime.** Ships all of the above. MIT licensed,
   self-hostable, provider-agnostic, MCP-native, with an `agentskills.io`-format
   skill system.

## Decision

Option 3.

## Trade-offs accepted

- **Hermes is 0.x.** No backwards-compatibility promise, and releases land every
  few days (v0.19.1 → v0.21.0 in roughly a month). Our surface area against it
  is therefore kept deliberately small: five CLI flags and one config file
  shape, each recorded with its source in `verified-facts.md`, and a runtime
  version report in `pfa doctor`.
- **We inherit its security model.** That is a feature, not a compromise: its
  approvals run inside the agent loop, which is the only place a permission
  check can actually block a call.
- **The original brief specified "Hermes 2.x", which does not exist.** Verified
  against the releases page: the project is at v0.21.0. We target 0.19–0.21.

## Consequence

The rule for this repository: **do not reimplement anything Hermes provides.**
When a feature is wanted, first check whether Hermes has it. If it does,
configure it. Roughly 1,300 lines of Python is the whole of what Hermes did not
already do.
