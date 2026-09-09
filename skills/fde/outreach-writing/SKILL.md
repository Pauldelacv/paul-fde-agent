---
name: outreach-writing
description: Procedure for writing cold outreach a specific person would answer - evidence-based personalisation, one ask, honest framing, opt-out and deliverability
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, outreach, copywriting, email, prospecting]
    category: fde
---

# Outreach Writing

A procedure for writing the message itself. It assumes the list is already
sourced, verified and lawful — `lead-generation` and `gdpr-compliance` do that
— and concerns only what the recipient reads.

## When to Use

Use this when the deliverable is a message to a named prospect: a first-touch
email, a follow-up, a connection note, a reply to a lukewarm answer. It is
explicit-only (`--skill outreach-writing`), because most prospecting tasks are
sourcing and list work that produce no copy at all.

Do not use it for messages to people who already know you. Those are just
email, and this procedure's caution about familiarity will make them stilted.

## The Non-Negotiable Rules

1. **Never claim a fact you have not verified.** Not the company's headcount,
   not their stack, not their funding, not "I saw your post" if you did not.
   Every personalised sentence traces to a source named in the draft.
2. **Never fake a relationship.** No invented referral, no "following up on our
   conversation" where there was none, no fake re-send of an email never sent.
   This is not a style rule — it is a lie to a stranger about a shared past.
3. **One ask, and make it small.** A cold message asks for a reply or fifteen
   minutes. It does not ask for a purchase, a demo of unspecified length, or a
   forwarded introduction.
4. **Every message carries a working opt-out and the Article 14 information.**
   No exceptions, follow-ups included. See `gdpr-compliance` steps 5–7.
5. **Write for one person.** If a sentence would survive unchanged in a message
   to a different company, it is not personalisation and it is doing nothing
   but taking up the reader's attention.
6. **Say what you sell.** Curiosity-gap openers that hide the offer read as
   manipulation to the exact senior audience that has seen them a hundred
   times.

## Procedure

### Before writing

1. **State the trigger in one sentence**, with its source. "They posted a role
   for a data engineer mentioning GDPR" — source, date. If you cannot write
   that sentence, there is no message to write; return to sourcing.
2. **State what this person's day contains** that the offer touches. Not the
   company's problem — theirs, in their role. The buyer of a security review
   and the buyer of a cost reduction are different people even at the same
   company.
3. **Decide the one outcome you want** from this message. Usually: a reply
   saying whether this is relevant.

### Structure

4. **Subject line: specific, lowercase-plain, no promise.** Four to seven
   words, naming the thing, not the benefit. It should read like a colleague
   wrote it, not like a campaign. No "Quick question", no first name in the
   subject, no emoji, no re-send trick.
5. **First sentence: the observation.** The trigger from step 1, stated as an
   observation and not as flattery. This is where the reader decides whether to
   continue, and it is the only sentence you cannot make generic.
6. **Second and third sentences: the connection.** What that observation
   implies about a problem they may have, and what you do about it — in their
   vocabulary, not your feature names. This is the whole argument; if it needs
   a fourth sentence, it is not sharp enough yet.
7. **One line of evidence, if you have it.** A comparable situation, a concrete
   result, or a specific capability. No unnamed "a client of ours" statistics —
   an unverifiable number is worse than no number.
8. **The ask, as a question they can answer with one word.** "Is this something
   you are looking at this quarter?" beats "Would you be open to a 30-minute
   call to explore synergies?" — the second asks for a calendar decision from
   someone who has not yet decided if they care.
9. **Signature, then the notice and the opt-out.** Real identity, real company,
   real address, working link.

### Length and tone

10. **Under 120 words in the body.** Cold email is read on a phone, between two
    other things. Cut every sentence that is not the observation, the
    connection, the evidence or the ask.
11. **Write plainly.** No "I hope this email finds you well", no "reaching
    out", no "circling back", no three-adjective value propositions. Short
    words, active voice, no exclamation marks.
12. **Match the recipient's language,** and if you are not fluent in it, say so
    rather than producing a translation that reads as machine output. In
    French, use *vous*, and keep the register professional rather than the
    Anglo-Saxon first-name familiarity.
13. **Never fabricate urgency.** No fake deadlines, no invented scarcity, no
    "last chance". The recipient can verify all three are false, and will.

### Follow-ups

14. **Two follow-ups, maximum, then stop.** Spaced several days apart. After
    the second, the answer is no; treat silence as the answer it is.
15. **Every follow-up adds something new** — a different angle, a relevant
    piece of work, a shorter ask. "Bumping this to the top of your inbox" adds
    nothing and reads as entitlement to their attention.
16. **Any negative reply ends the sequence and goes to the suppression list.**
    Including a soft one. "Not right now" means stop this sequence, not send
    the next step.

### Before handing over

17. **Label each personalised claim with its source** in the draft's notes, so
    the reviewer can check it in seconds.
18. **Re-read as the recipient.** A stranger, mid-task, who owes you nothing.
    Would they answer? If the honest answer is no, the draft is not finished.
19. **Hand it to a person to send.** Every time.

## Output Template

```
## Prospect
<name>, <role> at <company> — <verified address> (verified <YYYY-MM-DD>)

## Trigger
FACT: <observation> — source <url or document>, seen <YYYY-MM-DD>

## Draft
Subject: <4-7 words, specific>

<observation — one sentence, specific to them>
<connection — what it implies, and what you do about it>
<evidence — one line, or omitted if you have none that is real>
<ask — answerable in one word>

<signature>
<Article 14 notice + working opt-out link>

## Claims and their sources
| Claim in the draft | Source | Checked |
|---|---|---|

## Sequence
Follow-up 1: <date>, angle <...>
Follow-up 2: <date>, angle <...>
Then stop.

## Status
Draft awaiting human review. Not sent.
```

## Pitfalls

- Personalisation that is a mail-merge field wearing a coat: "I see you work at
  {{company}}".
- Complimenting the company's website. Everyone does it and it signals a
  template.
- Claiming to have read something you did not.
- Two asks, or an ask that requires a diary.
- A subject line written to be opened rather than to be accurate.
- Statistics with no attributable source.
- Fake urgency, fake referrals, fake re-sends of messages never sent.
- Follow-ups that only say "just checking in".
- Continuing a sequence after a soft no.
- A translated message nobody fluent has read.
- Any draft that leaves without a tested opt-out.

## Verification

Before delivering, check: every factual claim appears in the sources table with
a date; nothing implies a prior relationship; the body is under 120 words;
there is exactly one ask and it is answerable in a word; the subject names the
subject; the notice and opt-out are present and the link is real; the draft is
marked as awaiting review and has not been sent.
