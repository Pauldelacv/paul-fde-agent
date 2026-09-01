# ADR 0004 — One runtime dependency

**Status:** Accepted · **Date:** 2026-09-01

## Problem

The obvious stack for a Python CLI is `click`/`typer` + `pydantic` + `rich` +
`requests`. Each is excellent. Together they are four dependency trees to
audit, update and explain, in a project whose own code is ~1,300 lines.

## Decision

Runtime dependencies: **`PyYAML`**, and nothing else.

| Rejected | Replaced by | Reasoning |
|---|---|---|
| `click` / `typer` | `argparse` | Seven subcommands with flags. argparse does this; the CLI is ~280 lines. |
| `pydantic` | hand-written validator | ~40 config keys. Our validator is ~90 lines and every message names the offending key *and* the remedy — better DX than a generic schema error. |
| `requests` | `urllib` | One healthcheck GET. |
| `rich` | ANSI escapes behind an `isatty()` check | Cosmetic. Hermes owns the interactive UI. |

`PyYAML` earns its place: the routing policy and the Hermes config are both
YAML, and Hermes itself uses YAML, so this aligns us with the runtime we sit on.

## Trade-offs accepted

- argparse is more verbose than typer, and its errors are less pretty.
- The validator is code we own and must maintain. It is also code that produces
  the error messages we want, which was the point.

## Consequence

`pip install paul-fde-agent` pulls one package. The test suite runs in about a
second. A reader can hold the whole dependency surface in their head — which is
the actual goal, since this repository is meant to be *read*.
