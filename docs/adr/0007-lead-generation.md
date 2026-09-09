# ADR 0007 — Lead generation runs locally, drafts only, and refuses to act without provenance

**Status:** Accepted · **Date:** 2026-09-09

## Problem

The first vertical this agent is being pointed at is the freelance practice it
belongs to: selling the installation of self-hosted, GDPR-respecting AI agents
connected to a company's tools over MCP. Prospecting for that is a good first
workload, and it is also the most dangerous one this project has taken on.

Every previous task category operated on text the operator supplied about
systems. This one operates on **named living people**, which changes three
things at once:

- The data is regulated. A prospect list is personal data, and a work address
  of the shape `firstname.lastname@company.com` is not an exception to that.
- The output is an action on the outside world. Everything before this produced
  an answer for the operator to read; an outreach message is sent to a stranger
  and cannot be unsent.
- The failure mode is other people's, not ours. A wrong routing decision costs
  tokens. A message to someone who asked never to be contacted again is a
  breach of their rights, and it is also the end of the sender's reputation.

There is also a straightforward credibility problem. It is not possible to sell
GDPR-respecting installations using a prospecting pipeline that is not one.

## Options

### Where the prospect data is processed

1. **Cloud model.** Best copy. Every prospect's name, role, employer and
   address is then sent to a third party, which becomes a processor to contract
   with and, usually, a transfer outside the EEA to document.
2. **Local model.** Weaker copy from `gemma4:e4b`. The list never leaves the
   machine.

### What the agent is allowed to do

3. **Draft and send**, with approvals on the send step.
4. **Draft only**, with no send path in the code at all.

## Decision

**Local model (2), draft only (4).**

### Local, because the alternative is a contract

`routes.prospecting` is pinned to `local/gemma4:e4b`. This is the one route in
the policy where the provider is a compliance decision rather than a cost one,
and the policy file says so where someone editing it will read it.

A hosted model would be better at the writing. It would also mean naming that
provider as a processor in the Article 30 record, holding an Article 28
contract with them, and documenting the transfer — three obligations that
simply do not arise when the data stays on the box. For a practice whose offer
is "your data stays on infrastructure you control", the local route is not a
compromise; it is the product working.

The trade-off is real and is not hidden: e4b writes weaker copy. Changing the
route is one line, and both the policy comment and this ADR say what has to be
true before it is changed.

### Draft only, because approval is not a boundary

There is no send path in `src/pfa/leads.py`. Not a disabled one, not one behind
a flag, not one gated on an autonomy level — none. `draft_for` writes a file.
A test asserts the module imports no transport and exposes no function whose
name begins with `send`.

This is the same reasoning as ADR 0003's autonomy levels, applied harder. A
permission check outside the agent loop cannot block a call; the reliable way
to guarantee an agent does not send email is for it to have no way to send
email. The lemlist connector's tool exclusions point the same direction, and
are honest about being a weaker measure — lemlist's generic `call_api` tool can
still reach a send endpoint, which is exactly why the guarantee lives in code
that has no HTTP client rather than in a tool filter.

What this costs: the operator reviews and sends. That is not friction to be
optimised away later. A person reading each message before a stranger does is
the control that makes the rest of it safe, and the day it becomes tedious is
the day the volume is wrong.

### Provenance is a hard gate, quality is not

A prospect row is refused — not warned about, refused — when it has no
`source` or no `collected_at`. The reasoning is that Article 14 requires
telling someone where their data came from, so a row without a source describes
a person who cannot lawfully be contacted at all. No amount of good copy fixes
that.

A missing `trigger` is only a warning. It produces a weak message, and a weak
message is a quality problem the operator may knowingly accept.

The distinction is the fact/hypothesis discipline in another form: a
compliance blocker is a fact about what may happen, and a quality warning is a
judgement the operator gets to make.

### Suppression is checked first, and twice

Before enrichment, before drafting, before a prospect is listed. `draft_for`
re-checks it even after `preflight` already has — the two look redundant and
are not, because `draft_for` is importable and the guarantee has to hold for a
caller that never ran the preflight.

The suppression file is append-only in practice: `Suppression.add` appends
rather than rewriting, so a partial write cannot lose an entry. It is also the
one record an erasure request does not empty, and `gdpr-compliance` explains
why keeping it is both lawful and necessary.

### Three skills, two attached

`lead-generation` and `gdpr-compliance` are attached to the `prospecting`
category. Both pass ADR 0005's test — they apply to the *whole* category, since
every prospecting task runs the pipeline and every one of them touches personal
data.

`outreach-writing` is explicit-only, like `api-integration`. Sourcing, list
hygiene and enrichment review are prospecting tasks that produce no copy, and a
writing procedure loaded for them is context spent making the model less
focused. `pfa leads draft` attaches it itself, so the one path that always
writes copy always has it.

### The classification rules run first

`prospecting` is evaluated before every other rule. Its keywords are domain
nouns rather than ordinary English, so a false positive means someone actually
wrote "prospect", "ICP" or "lemlist". Placed later, "design a cold email
sequence" would be captured by `architecture`'s "design a" and "the outreach
campaign stopped working" by `debugging`.

Bare "lead" and bare "campaign" are deliberately absent, for the same reason
`coding` omits bare "issue": they are ordinary words that would hijack
unrelated tasks.

## Trade-offs accepted

- **e4b writes weaker copy than a frontier model.** Stated above; a one-line
  change with three documented obligations attached.
- **"Debug the lemlist webhook" now classifies as prospecting**, because the
  prospecting rules run first. It attaches the wrong procedures to a debugging
  task. `pfa route` shows it before anything runs and `--task debugging`
  overrides it; a misclassification that is visible and cheap beats one that is
  invisible.
- **Prospect data lives on a Docker volume, not a bind mount.** The container
  runs as uid 10001, and a bind-mounted host directory owned by anyone else is
  unwritable in a way Docker reports only at the first write. `make leads-pull`
  and `make leads-push` move files instead. Clumsier than editing in place, and
  it works on every host.
- **CSV, not a database.** A hand-maintained list of a few dozen people is a
  file someone edits in a spreadsheet. Postgres arrives with the memory layer,
  and moving this into it before then would add a migration to a table nobody
  has filled.
- **The compliance checks are structural, not legal.** The code can verify a
  source was recorded; it cannot verify the source is true, that the balancing
  test is sound, or that the national marketing rules were read. The
  `gdpr-compliance` skill states plainly that it is a procedure and not legal
  advice, and routes the questions it cannot answer to a human.
- **Nothing verifies an address.** Verification is lemlist's job through the
  connector, and the shape check in `leads.py` is explicitly a check for a
  mangled CSV cell. A regular expression has never established that an address
  exists, and treating one as verification is how a domain's reputation dies.
