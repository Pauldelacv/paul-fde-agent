---
name: technical-writing
description: Procedure for written deliverables - client summaries, decision records, handovers - that a non-specialist can act on
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, writing, communication, adr, reporting]
    category: fde
---

# Technical Writing

A procedure for the artefact the client actually keeps: the summary, the
decision record, the handover, the status note. The engineering is judged
through this document, so a correct fix explained badly is a fix that does not
get credited — or worse, gets undone.

## When to Use

Use this whenever the output is prose someone else will read and act on: a
client-facing summary, an incident write-up, a decision record, a handover, a
recommendation, a status update. It scales — see *Sizing* — so it applies to a
three-line update as well as a ten-page report.

## The Non-Negotiable Rules

1. **Name the reader before the first sentence.** What they know, what they must
   decide, what they will do next. Every later choice follows from this.
2. **Label every claim**, exactly as `fde-methodology` requires: FACT,
   HYPOTHESIS, CONCLUSION, ACTION TAKEN, ACTION RECOMMENDED. Prose is where
   hedged language quietly promotes a hypothesis into a fact; labelling is what
   stops it.
3. **Say what you do not know.** A document with no uncertainty section is
   claiming there is none, and that claim is nearly always false.
4. **No blame.** Describe systems and decisions, never people. "The webhook
   handler had no signature check" — not "the previous team forgot".

## Sizing

The structure is fixed; the length is not.

- **Status update (3–10 lines):** Answer, what changed, what is next. Labels
  still apply.
- **Client summary (half a page):** Answer, what happened, what was done, what
  happens next, what is not yet known.
- **Full report / decision record:** every section of the template.

Writing a full report where an update was asked for is a failure of the same
kind as the reverse.

## Procedure

1. **Write the reader profile in one line**, for yourself. "The client's ops
   lead, non-engineer, needs to decide whether to keep the sync paused." Delete
   it before delivery; it does its work during drafting.
2. **Write the answer first.** The first paragraph says what happened and what
   to do. Not the background, not the method, not the chronology. If the reader
   stops after two sentences, they should still have the thing they needed.
3. **Draft the structure before the prose.** Headings only, then check them
   against the reader profile. A section that serves no decision comes out now,
   cheaply.
4. **Fill in, labelling as you go.** Every FACT carries its evidence inline.
   Every recommendation carries its rationale, its risk and its rollback.
5. **Convert every hedge into a label.** Search the draft for "probably",
   "likely", "seems", "appears", "should be", "I think". Each one is either a
   HYPOTHESIS (say so) or a FACT you have not yet sourced (go source it).
6. **Cut jargon or define it once.** Internal names, acronyms, service names
   mean nothing outside the team. Where a term must stay, define it at first use
   in one clause.
7. **Put the numbers in.** "Slow" is not a finding; "the p95 went from 200ms to
   9s between 14:00 and 16:00 UTC on 12 March" is. Every number carries its unit
   and its timezone.
8. **Write the uncertainty section**, and make it specific: what you could not
   determine, what access or time would close it, and how much the
   recommendation depends on it.
9. **Read it once as the reader.** Can they act? Do they know what is being
   asked of them and by when? Is there a sentence they would have to ask about?
10. **Cut ten percent.** Almost always the throat-clearing at the top of each
    section, and adjectives doing no work.

## Output Template

```
## Summary
<two to four sentences a non-engineer can act on: what happened, what it
affected, what was done, what is needed from them>

## What we found
- FACT: <observation> [source: <log / query / test / document>]
- HYPOTHESIS: <candidate> — status: untested | supported | refuted

## What was done
- ACTION TAKEN: <what> — effect: <observed result>

## What we recommend
- ACTION RECOMMENDED: <what> — why: <rationale> — risk: <what it costs if
  wrong> — rollback: <how to undo>

## Decision required from you
- <the decision, the options, the deadline, the default if no answer>

## What we could not determine
- <gap> — <what access or time would close it> — <what it changes if wrong>

## Detail
<the technical narrative, for the reader who wants it; nothing above depends
on anyone reading this section>
```

For a **decision record** (ADR), replace the middle sections with: Context,
Options considered (two or three, each with its trade-off), Decision, and
**Consequences accepted** — the last being the one people omit and the one that
matters in a year.

## Pitfalls

- Chronology instead of conclusion: "First I checked the logs, then I…". The
  reader wants the answer, not the walk.
- Burying the decision request in the middle of a paragraph.
- Hedged language standing in for an honest HYPOTHESIS label.
- Jargon that is invisible to you because it is your daily vocabulary.
- Numbers without units, timezones, or a baseline to compare against.
- An empty or missing "could not determine" section.
- Apologising. State the facts and the fix; an apology in a technical document
  reads as an admission of a fault that may not exist.
- Passive voice hiding who does the next step. "The credentials will be
  rotated" — by whom, by when?

## Verification

Before delivering, check: the first paragraph answers the question on its own;
every claim carries a label; every hedge has been resolved into a label or a
source; every number has a unit and a timezone; the decision asked of the reader
is stated in one sentence with a deadline; the uncertainty section exists and is
specific; no sentence assigns blame to a person.
