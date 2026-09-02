---
name: technical-research
description: Procedure for technical research and veille that produces sourced, dated claims rather than confident summaries
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, research, veille, evaluation]
    category: fde
---

# Technical Research

A procedure for answering "what is the state of X, and what does it mean for
us?" in a way a client can act on and a colleague can re-check six months later.

## When to Use

Use this for technology landscape reviews, tool and vendor comparison, veille on
a moving ecosystem, "should we adopt X", and any question whose answer will be
quoted back to you later. Do not use it for questions with a single documented
answer — look those up and cite the doc.

## The Non-Negotiable Rule

**A claim without a source and a date is not a finding, it is a memory.**

Every statement in the output carries three things:

- **CLAIM** — what is asserted.
- **SOURCE** — where it came from: a URL, a doc section, a release page, a
  command you ran. "The docs say" is not a source; the page is.
- **CHECKED** — the date you saw it.

Two further labels, used exactly as in `fde-methodology`:

- **FACT** — verified against a primary source.
- **HYPOTHESIS** — inferred, plausible, unverified. Says so in the output.

Model training data is not a source. It is a *lead*: something to go and check.
A version number, a price, a feature list or a limit recalled from training is
a HYPOTHESIS until a primary source confirms it, and in a moving ecosystem it is
usually a stale one.

## Source Hierarchy

Prefer sources in this order, and say which tier a claim came from when it
matters:

1. **Primary, machine-readable** — the package index API, the releases page, the
   OpenAPI schema, the source repository, the pricing page.
2. **Primary, human-written** — official documentation, changelogs, RFCs, the
   vendor's own announcement.
3. **Secondary, attributable** — a maintainer's post, a conference talk, a
   named engineer's write-up.
4. **Secondary, unattributable** — blog roundups, listicles, SEO content, model
   recollection. Usable to find leads. Never usable as the only support for a
   claim you deliver.

Where tier 1 disagrees with tier 3, tier 1 wins and the disagreement is worth a
line in the output: it usually means something changed recently.

## Procedure

1. **State the decision behind the question.** Research with no decision
   attached expands without limit. Write down what will be done differently
   depending on the answer. If nothing will, stop and say so.
2. **Write the questions.** Three to seven specific, answerable questions.
   "Is Hermes any good" is not answerable. "Does Hermes support routing a user
   request to a different model by task category" is.
3. **Define the criteria before looking.** Licence, maintenance signal, release
   cadence, dependency weight, operational cost, exit cost. Fixing criteria
   first is what stops the comparison being retro-fitted to whichever tool you
   happened to like.
4. **Collect, tier by tier.** Start at tier 1. Record every source with its URL
   and the date. Note the version or date of the artefact itself, not just when
   you looked.
5. **Check freshness.** For anything versioned, resolve the *current* version
   from a primary source. Ecosystems move; a six-month-old comparison is often
   wrong in the one respect that matters.
6. **Look for the disconfirming source.** For each preliminary conclusion, spend
   one search actively trying to find something that contradicts it. Record
   what you found, including "nothing contradicting this was found", which is
   itself a weak but real signal.
7. **Separate what you verified from what you inferred.** Anything not traced to
   a source becomes a HYPOTHESIS in the output, explicitly.
8. **Compare against the criteria from step 3.** One row per option, one column
   per criterion, cells that say "unknown" where they are unknown.
9. **Answer the decision.** A recommendation with its condition ("if the
   constraint is X, then A; if it is Y, then B"), the cost of being wrong, and
   what would change the answer.
10. **Record the gaps.** What you could not verify, what access or time would
    close it, and how much the recommendation depends on it.

## Output Template

```
## Question and decision
<the decision this informs; what changes depending on the answer>

## Answer
<three sentences, plainly. The recommendation and its condition.>

## Findings
- FACT: <claim>
  - source: <url or artefact> — checked: <YYYY-MM-DD> — tier: <1-4>
- HYPOTHESIS: <claim> — basis: <inference> — how to verify: <what to check>

## Comparison
| Option | <criterion> | <criterion> | Licence | Maintenance | Exit cost |
|---|---|---|---|---|---|
| A | ... | ... | ... | last release YYYY-MM-DD | ... |

## What would change this answer
- <the condition, and which finding it hangs on>

## Not verified
- <claim I could not source, and what would settle it>

## Sources
- <url> — <what it establishes> — checked YYYY-MM-DD
```

## Pitfalls

- Reporting a version number, price or limit from memory. This is the single
  most common way technical research is wrong, and it is wrong confidently.
- Letting the criteria be chosen after the options, which produces a comparison
  that is really an argument.
- Treating a well-written blog post as a primary source because it is well
  written.
- Omitting dates. A sourced claim with no date decays invisibly.
- Answering a broader question than was asked because the material was there.
- Presenting an absence of evidence as evidence of absence. "I found no
  support for X" and "X is unsupported" are different claims; say which one
  you mean.

## Verification

Before delivering, check: every FACT has a URL and a date; every version number
was resolved from a primary source during *this* research, not recalled; the
"Not verified" section is non-empty or its emptiness is deliberate and stated;
the recommendation names the condition under which it flips.
