# ADR 0002 — Route by task category at session launch

**Status:** Accepted · **Date:** 2026-09-01

## Problem

Running every task on a strong cloud model is expensive; running every task on a
small local model produces poor results on hard reasoning. We want cheap local
inference for the bulk of daily work and cloud capability where it pays for
itself — without hardcoding a model anywhere.

Hermes' `auxiliary` config routes its *internal* side-tasks (context
compression, vision, title generation) to different models. It has no notion of
routing the *user's request* by what kind of task it is. Verified in
`verified-facts.md`.

## Options

1. **Patch Hermes to route per-turn.** Correct in principle: the model could
   change as a conversation shifts. Requires forking a 0.x project releasing
   every few days — a permanent maintenance cost with no exit.
2. **An MCP tool the agent calls to choose its own model.** Fits the MCP model
   nicely. Does not work: a running session cannot swap its own model in
   response to a tool result, so the tool returns advice nobody can act on.
3. **Classify before launch and pass `--model`.** Uses a documented, stable
   flag. Decision is made once, from the task text.

## Decision

Option 3. Classification is keyword rules in `config/routing.yaml`, evaluated in
order, first match wins, matched on word boundaries. `pfa run --task <category>`
overrides. `pfa route` shows the decision without spending anything.

Keyword rules rather than an LLM classifier: a classifier adds a model call,
latency and a failure mode to every request in order to pick between six
buckets. Rules are free, instant, deterministic, and readable by whoever has to
debug them.

## Trade-offs accepted

- **A session cannot change model mid-flight.** Research that turns into coding
  stays on the research model. Today's mitigation is `--task` or a second
  session. If the friction proves real in daily use, per-turn routing needs
  upstream support — revisit then, not before.
- **Rules miss unphrased tasks.** Anything with no keyword falls back to
  `default_task` (the cheapest route). `pfa logs` shows how often that happens,
  so the policy can be tuned from evidence.
- **Cost figures are only as good as the policy's pricing table.** Prices are
  operator-maintained placeholders, labelled as such in the file and in
  `router.estimate_cost`'s docstring.

## Why this is the simple option

The router is a pure function of (text, policy): no network, no state, no model
call. That is why it is ~100 lines and has 20 tests.
