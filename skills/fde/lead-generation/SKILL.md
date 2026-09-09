---
name: lead-generation
description: Procedure for building a B2B prospect list and taking it to reviewed, personalised outreach drafts - sourcing, enrichment, verification, segmentation and handoff
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, prospecting, outbound, enrichment, b2b]
    category: fde
---

# Lead Generation

A procedure for turning "we should find clients" into a small list of named
people with a verified address, a reason to be contacted, and a draft written
for them specifically.

## When to Use

Use this when the task is finding, qualifying or enriching prospects, or
preparing outreach to them. Pair it with `gdpr-compliance`, which the
`prospecting` route attaches alongside this one and which governs what is
lawful to do with the list. Pair it with `outreach-writing` (`--skill
outreach-writing`) when the deliverable is the message rather than the list.

## The Non-Negotiable Rules

1. **The agent drafts. A person sends.** Nothing in this procedure ends with a
   message leaving the building. The output is a draft for review, every time,
   including when the operator asks for it to be sent.
2. **Check the suppression list before anything else.** Before enriching,
   before drafting, before adding to any tool. Someone who has objected has
   objected permanently, and re-contacting them is both the worst outreach
   mistake and a breach of Article 21.
3. **Never invent an email address.** A pattern-guessed address is a
   HYPOTHESIS. It becomes a FACT only when a verification service returns
   valid, and it is recorded with the date it was checked. Guessed addresses
   bounce, and bounces destroy the sending domain everyone else's mail depends
   on.
4. **Never invent a fact about a prospect.** Every claim in a draft traces to a
   source you can name — their site, their post, their job listing, their
   changelog. A plausible-sounding detail that turns out to be wrong is worse
   than no personalisation at all.
5. **Enrichment costs money and quota.** Every enrichment call spends credits.
   Deduplicate and filter *before* enriching, never after.
6. **Twenty-five well-researched prospects beat a thousand scraped ones.** This
   is not a taste preference: volume is what triggers spam classification,
   exhausts a domain's reputation, and produces the complaint that ends the
   channel.

## Procedure

### Define the target before touching a tool

1. **Write the ICP as filters, not adjectives.** "Companies that care about
   security" is not an ICP. Industry, headcount band, geography, and one
   observable trigger are. If it cannot be expressed as a database filter, it
   cannot be sourced, and you will discover that after paying for the list.
2. **Name the buying role and the trigger separately.** Who signs, and what
   happened recently that makes now different from six months ago — a funding
   round, a hire, a compliance deadline, a migration, a job posting naming the
   problem you solve. No trigger means no reason for the message to exist.
3. **State the disqualifiers.** Company sizes you cannot serve, sectors you
   will not sell to, anyone already in a conversation. Write them down; they
   are the filter that keeps the list small enough to research properly.
4. **Record where the list will come from and on what basis it may be
   contacted** before sourcing it. `gdpr-compliance` step 1. A list you cannot
   describe the origin of is a list you cannot lawfully use, and finding that
   out afterwards means discarding the work.

### Source

5. **Query the database with the ICP filters**, in one narrow query rather than
   a broad one you plan to filter later. Record the exact filters used and the
   date — a list is a snapshot, and in six months nobody will remember which.
6. **Deduplicate against everything you already have**: existing prospects,
   current clients, past conversations, and the suppression list. Do this
   before enrichment, because enrichment is what costs.
7. **Cap the batch.** Take the first 25–50 that survive filtering. A larger
   batch is not more ambition; it is a guarantee that the research step gets
   skipped.

### Enrich and verify

8. **Enrich only the survivors.** Request exactly the fields the message needs
   — usually an email and a role. Do not request phone numbers you have no
   intention of calling; unused personal data is a liability with no upside,
   and `gdpr-compliance` step 4 forbids it.
9. **Treat enrichment as asynchronous and fallible.** These calls return a job
   id, not an answer. Poll for the result; handle "not found" as a normal
   outcome, not an error. A prospect with no findable address is dropped, not
   guessed at.
10. **Verify every address before it is used**, and record the verification
    date next to it. Accept only `valid`. Treat `catch-all`, `accept-all`,
    `risky` and `unknown` as unusable: a catch-all domain accepts everything
    and tells you nothing, so a "delivered" there is not evidence.
11. **Respect the rate limit.** These APIs limit per key and return
    `Retry-After` when you cross it. Honour the header rather than guessing a
    backoff, and never parallelise your way around it.
12. **Record the provenance of every prospect**: which source, which query,
    which date, which enrichment run. This is what the Article 30 record and
    the Article 14 notice are both built from, and it cannot be reconstructed
    later.

### Research, then draft

13. **Spend the research budget on evidence, not on more prospects.** Per
    prospect: their site, their recent public activity, their open roles, their
    stack if it is visible. You are looking for one specific, checkable
    observation that explains why this message is going to this person.
14. **Drop the ones with no trigger.** If nothing found gives a reason to write
    now, the prospect is not ready. Removing them is the step that makes the
    remaining drafts good.
15. **Draft one message per prospect**, following `outreach-writing`. Label
    each personalised claim with the source it came from, so the reviewer can
    check it in seconds rather than trusting it.
16. **Hand the drafts to a person.** Present them for review with the evidence
    attached. Their decision is per-prospect: send, edit, or drop. Loading
    them into a sending tool is a human action taken after that review.

### Track what happened

17. **Log the outcome per prospect** — bounced, no reply, replied, objected —
    and feed objections straight to the suppression list.
18. **Read the bounce rate as a stop signal.** Above a few percent, stop
    sending and fix verification. Continuing past that damages the sending
    domain for months, and no campaign is worth it.
19. **Judge the ICP by replies, not opens.** Open tracking is unreliable and is
    itself a processing activity you have to justify. Replies are the only
    honest signal about whether the targeting was right.

## Output Template

```
## ICP
Filters: <industry, size, geography, role>
Trigger: <what makes now different>
Disqualifiers: <who is excluded and why>

## Sourcing
Source: <database/tool> — query <exact filters> — run <YYYY-MM-DD>
Returned <n>; after dedupe and disqualifiers <n>; enriched <n>

## Prospects
| Name | Role | Company | Email | Verified | Source | Trigger observed |
|---|---|---|---|---|---|---|
| <name> | <role> | <company> | <address> | valid <YYYY-MM-DD> | <origin> | FACT: <observation> — source <url or doc> |

## Dropped, and why
- <name>: no trigger found / no verified address / on suppression list

## Legal basis
<from gdpr-compliance: basis, notice, retention, suppression checked YYYY-MM-DD>

## Drafts
<one per prospect, each claim traceable to the Trigger column>

## Awaiting human decision
<n> drafts ready. Nothing has been sent, and nothing will be by this agent.
```

## Pitfalls

- Sending. This procedure never sends; if the operator asks, produce the draft
  and say who has to press the button.
- Enriching before deduplicating, and paying twice for the same person.
- Accepting a `catch-all` result as a verified address.
- Guessing `firstname.lastname@` and treating the guess as an address.
- Personalising from the company's marketing copy, which says the same thing
  for every company in the sector and reads as a mail merge.
- A trigger that is not a trigger: "you are a growing company" is a
  compliment, not a reason to write.
- Sourcing a bigger list because the small one felt insufficient, then
  skipping the research that was the entire point.
- Skipping the suppression check because this batch is "a different campaign".
  It is the same person.
- Recording a prospect with no provenance, making the Article 14 notice
  impossible to write.
- Treating a bounce as bad luck rather than as a verification failure that
  will repeat.

## Verification

Before delivering, check: the suppression list was consulted and the date is
recorded; every address carries a verification status and date; every
personalised claim names a source; every prospect has a provenance record; the
legal basis section is filled in from `gdpr-compliance` and not left as a
heading; the deliverable is drafts awaiting review, and nothing has been sent.
