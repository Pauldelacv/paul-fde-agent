---
name: gdpr-compliance
description: Procedure for handling personal data lawfully in prospecting and agent work - legal basis, notice, minimisation, retention, suppression, processors and transfers
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, gdpr, privacy, compliance, prospecting]
    category: fde
---

# GDPR Compliance

A working procedure for the parts of the GDPR that a prospecting agent touches
every single run. It exists because this agent processes personal data by
design: a prospect list *is* personal data, including a work address of the
shape `firstname.lastname@company.com`.

## When to Use

Use this whenever a task touches personal data — which for prospecting is every
task, since a prospect list is personal data by definition. The `prospecting`
route attaches it automatically for that reason. Attach it by hand
(`--skill gdpr-compliance`) to any other work that handles data about people:
importing a client's user table, wiring an agent to a CRM, designing what a
system logs.

Use it *before* the data is collected, not before it is sent. Most of what goes
wrong here is decided at collection, and by the time a message is drafted the
expensive mistakes have already been made.

## This is a procedure, not legal advice

It encodes the steps and the questions. It does not decide the answers, and it
is not a substitute for a lawyer or a DPO. Two rules follow:

- **Every regulatory claim carries its source and the date it was checked.**
  Guidance changes; a citation with no date is worthless the year after.
- **Where the answer is genuinely unsettled, say so** and escalate to a human.
  A confident wrong answer about someone's rights is the expensive failure
  mode, and "the agent said it was fine" protects nobody.

## The Non-Negotiable Rules

1. **An objection is permanent and immediate.** Anyone who asks not to be
   contacted goes on the suppression list before any other work, and comes off
   it never.
2. **A work email address is personal data.** "It is a B2B address" changes
   which legal basis is available; it does not put the data outside the
   regulation.
3. **Collect only what the message needs.** Data you enriched because it was
   offered, and never used, is pure liability.
4. **Never process a special category of data** — health, political opinion,
   union membership, religion, sexual orientation, biometrics — for
   prospecting. There is no legitimate-interest route to it. If sourcing
   returns it, drop the field.
5. **No provenance, no processing.** A prospect whose origin you cannot state
   cannot be given the Article 14 notice, so they cannot lawfully be
   contacted. Discard them.

## Procedure

### Establish the basis before collecting anything

1. **Name the legal basis, in writing, per processing activity.** For B2B
   prospecting the usual basis is legitimate interest (Article 6(1)(f)). It is
   not automatic: it requires a balancing test, and it is unavailable for
   special-category data.
2. **Write the balancing test down** — three questions, three answers, dated
   and kept: what is the interest; is the processing necessary for it, or would
   less intrusive processing do; would this person reasonably expect a message
   of this kind in their professional role. If the third answer is no, the
   basis fails and no amount of drafting fixes it.
3. **Check the marketing rules separately from the GDPR.** Electronic marketing
   is governed by national ePrivacy implementations as well, and they differ:
   the rules for messaging an individual consumer are typically stricter than
   for messaging a named person in their professional role at a business, and
   the boundary is a national question. VERIFY the current position for the
   country you are sending to, with the regulator's own text, and record the
   date. Do not carry over an answer from another market.
4. **Minimise at the point of collection.** Decide which fields the message
   actually needs, and request only those. Declining an offered phone number is
   the cheapest compliance decision available.

### Tell people, because they did not give you their data

5. **Article 14 applies to every prospect on the list.** The data came from a
   database or a website, not from them, so they must be told — at the latest
   when you first make contact. In practice the first message carries it.
6. **The notice must say, plainly**: who you are, why you are writing, the
   legal basis, where their data came from (the actual source, by name), how
   long you will keep it, and how to object or to ask for erasure. A footer
   with a real link is enough; a footer with no source named is not.
7. **Make objecting easier than replying.** One click, working, in every
   message. An unsubscribe link that fails is worse than none: it converts a
   quiet objection into a complaint to the regulator.

### Honour rights, immediately

8. **Suppression is checked first, always** — before enrichment, before
   drafting, before importing into any tool. Every run, not every campaign.
9. **Keep the suppression list forever, and keep it minimal.** Storing an
   address in order to never contact it again is lawful and necessary; that is
   the one record erasure does not empty. Store the address and the date,
   nothing else.
10. **Route every rights request to a human within the day.** Access, erasure,
    rectification, objection, portability. The regulation gives you a month;
    the agent's job is to recognise the request and escalate it, never to
    answer it. Recognise it however it arrives — "stop emailing me" in a reply
    is an objection, not a bounce.

### Keep the record

11. **Maintain the Article 30 record** of processing activities: purpose,
    categories of data, categories of people, recipients, transfers, retention,
    security measures. It is the first thing a regulator asks for and it cannot
    be written retrospectively.
12. **Log every processor** you send personal data to: the enrichment provider,
    the sending platform, the model provider if the data reaches one. Each needs
    an Article 28 contract in place *before* the first record is sent.
13. **Watch the transfer question.** Personal data leaving the EEA needs an
    adequacy decision or Article 46 safeguards. This is the reason the
    prospecting route runs on a local model: a prospect list that never leaves
    the machine has no transfer to document, no processor to contract with, and
    no sub-processor to audit. Changing that route to a hosted model is a
    compliance decision, not a quality one.
14. **Set a retention period and enforce it with a job, not a promise.**
    Prospect data kept "in case it becomes useful" has no basis. Pick the
    period, write it in the notice and the record, and delete on schedule —
    including from the sending tool, which is a separate copy.

### Before anything is sent

15. **Run the checklist and record the answers**: basis named; balancing test
    dated; national marketing rules checked and dated; notice present and
    complete with the source named; opt-out present and tested; suppression
    checked; provenance recorded per prospect; retention set; processors under
    contract; transfers documented.
16. **Any "no" stops the send.** Report it as a blocker with the specific
    remedy. Do not proceed with a note in the summary.

## Output Template

```
## Processing activity
Purpose: <what and why>
Data: <fields held — the minimum the message needs>
People: <categories, e.g. named professional contacts at target companies>
Source: <where the list came from, by name>

## Legal basis
Basis: <Article 6(1)(x)> — decided <YYYY-MM-DD>
Balancing test:
  Interest: <...>
  Necessity: <why less intrusive processing will not do>
  Expectation: <why this person would expect this message in this role>
National marketing rules: <position> — source <regulator's own text> — checked <YYYY-MM-DD>

## Notice (Article 14)
Delivered: <where — e.g. first message footer>
States: identity / purpose / basis / source / retention / how to object  [all present? yes/no]

## Rights
Suppression list: <path> — <n> entries — checked <YYYY-MM-DD>
Requests received this run: <n> — escalated to <who> on <date>

## Processors and transfers
| Processor | What it receives | DPA in place | Location | Safeguard |
|---|---|---|---|---|

## Retention
Prospect records: <period> from <event>. Enforced by <mechanism>.

## Checklist
[ ] basis  [ ] balancing test  [ ] national rules  [ ] notice  [ ] opt-out tested
[ ] suppression checked  [ ] provenance per prospect  [ ] retention  [ ] DPAs  [ ] transfers

## Blockers
<any unchecked box, with the remedy. Any blocker stops the send.>

## Not determined
<questions that need a lawyer or a DPO, stated as questions>
```

## Pitfalls

- Treating "B2B" as an exemption. It changes the available basis, not the
  applicability.
- Writing the balancing test after deciding to send. It is a test, not a
  justification.
- Copying a compliance answer across borders because both are in Europe.
- Omitting the source from the notice, which is the one field people forget and
  the one Article 14 is specifically about.
- An unsubscribe link that is not tested end to end.
- Keeping enriched fields the message never used.
- Deleting an address in response to an erasure request and thereby losing the
  suppression entry, so the same person is contacted again next quarter.
- Sending prospect data to a hosted model without checking whether the provider
  is under contract as a processor.
- Retention "as long as necessary", with no period and no job.
- Letting the agent answer a rights request. It escalates; a person answers.

## Verification

Before delivering, check: every regulatory statement carries a source and a
check date; the legal basis is named with a dated balancing test; the notice
lists the actual source of the data; the opt-out has been tested, not assumed;
the suppression list was checked this run; every prospect has provenance; the
retention period is a number with a mechanism; unresolved questions are in
"Not determined" and escalated rather than answered.
