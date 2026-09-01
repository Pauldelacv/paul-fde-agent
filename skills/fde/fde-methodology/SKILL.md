---
name: fde-methodology
description: Structured problem-solving procedure for Forward Deployed Engineers
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, methodology, debugging, discovery]
    category: fde
---

# FDE Methodology

A generic, client-agnostic procedure for taking a reported problem from "something
is broken" to "here is the cause, the fix, and an explanation the client can read".

## When to Use

Use this whenever a problem arrives from outside your own codebase: a client
report, a failing integration, an unexplained production behaviour, a vague
complaint ("the sync is slow"). Do not use it for well-specified implementation
tasks — those are ordinary engineering work.

## The Non-Negotiable Rule

Label every statement. A reader must be able to tell, without asking, which
category each sentence belongs to:

- **FACT** — observed directly, with a source (a log line, a query result, a
  reproduction). A fact carries its evidence.
- **HYPOTHESIS** — a candidate explanation that has not yet been tested.
- **CONCLUSION** — a hypothesis that survived a test, with the test named.
- **ACTION TAKEN** — something already done, and its effect.
- **ACTION RECOMMENDED** — something proposed, not yet done.

Never promote a hypothesis to a fact because it is plausible, because it is the
only one you have, or because time is short. A wrong confident answer costs far
more than an honest "not yet established" — with clients, it costs the mandate.

## Procedure

1. **Understand** — Read the report. List what is actually claimed versus what
   is inferred. Note what the reporter did *not* say.
2. **Reformulate** — Restate the problem in your own words and get agreement.
   Most of the value an FDE adds is discovering the stated problem is not the
   real one. Stop here if reformulation changes the problem.
3. **Identify systems** — Enumerate every component on the path: services,
   databases, queues, third-party APIs, network boundaries, auth layers.
   Mark which you can observe and which are opaque.
4. **Collect** — Gather logs, metrics, error payloads, request IDs, schema,
   versions, recent deploys, config diffs. Record timestamps and timezones.
   Note explicitly what you could not obtain.
5. **Reproduce** — Attempt the smallest reproduction. If you cannot reproduce,
   say so plainly and continue; an unreproduced problem constrains every later
   conclusion and that constraint must be stated.
6. **Hypothesise** — Write at least three candidate causes. One hypothesis is
   not an investigation, it is a guess with extra steps. Include at least one
   that would be embarrassing (misconfiguration, wrong environment, clock skew,
   caching, a retry storm).
7. **Test** — For each hypothesis, define the observation that would *refute*
   it, then look for that observation. Prefer tests that discriminate between
   hypotheses over tests that confirm your favourite.
8. **Identify root cause** — Only once a hypothesis survived a refutation
   attempt. Distinguish the root cause from the trigger and from the symptom.
9. **Propose** — Give the minimal fix, plus alternatives with trade-offs and a
   recommendation. State the blast radius and the rollback path.
10. **Implement** — Only with authorisation, on a branch, never on main.
    Respect the configured autonomy level.
11. **Test the fix** — Show the original failure reproducing before, and not
    reproducing after. A fix without that pair is an assertion, not a fix.
12. **Document** — Record cause, evidence, fix, and what would have caught it
    earlier.
13. **Client summary** — Write for a non-specialist: what broke, what it
    affected, what was done, what happens next. No jargon, no blame, no
    speculation presented as certainty.

## Output Template

```
## Summary
<two sentences a non-engineer can act on>

## Facts observed
- FACT: <observation> [source: <log/query/repro>]

## Hypotheses considered
- HYPOTHESIS: <candidate> — status: refuted | supported | untested
  - refuting observation sought: <what would disprove it>

## Root cause
CONCLUSION: <cause> — established by <test>
(If not established: "Not established. Best-supported hypothesis: <x>.")

## Actions taken
- ACTION TAKEN: <what> — effect: <observed result>

## Recommended next
- ACTION RECOMMENDED: <what> — rationale, risk, rollback

## What I could not determine
- <explicit gaps, and what access would close them>
```

## Pitfalls

- Skipping step 2 and solving the stated problem instead of the real one.
- A single hypothesis, confirmed rather than challenged.
- Reporting a correlation found in logs as a cause.
- Silently omitting the "could not determine" section — an empty gap list is
  itself a claim, and usually a false one.
- Fixing on main because the change "is small".

## Verification

Before delivering, check: every sentence is labelled; the root cause section
either names its test or admits it is unestablished; the gaps section exists.
