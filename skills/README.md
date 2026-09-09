# The FDE skill library

Procedures the agent follows, in [agentskills.io](https://agentskills.io)
format: YAML frontmatter, then Markdown. This is the format Hermes reads from
`$HERMES_HOME/skills/<category>/<name>/SKILL.md` — nothing here is a
project-specific dialect, so any skill in this directory is portable to another
Hermes installation unchanged.

## Why skills rather than prompts

Good FDE work is methodical, and the method should not depend on what the model
improvises today. A skill puts the procedure in version control, where it can be
reviewed, diffed, and blamed when it turns out to be wrong.

## What is here

| Skill | Applies to | Attached automatically to |
|---|---|---|
| [`fde-methodology`](fde/fde-methodology/SKILL.md) | Taking a reported problem to a root cause | `debugging` |
| [`technical-research`](fde/technical-research/SKILL.md) | Landscape reviews, tool comparison, veille | `research` |
| [`github-workflow`](fde/github-workflow/SKILL.md) | Working in a repository that is not yours | `coding` |
| [`api-integration`](fde/api-integration/SKILL.md) | Third-party APIs, webhooks, integrations | — explicit only |
| [`technical-writing`](fde/technical-writing/SKILL.md) | Client summaries, decision records, handovers | `summarization`, `architecture` |
| [`lead-generation`](fde/lead-generation/SKILL.md) | Sourcing, enriching and qualifying prospects, to reviewed drafts | `prospecting` |
| [`gdpr-compliance`](fde/gdpr-compliance/SKILL.md) | Handling personal data lawfully: basis, notice, rights, retention | `prospecting` |
| [`outreach-writing`](fde/outreach-writing/SKILL.md) | Cold messages a specific person would answer | — explicit only |

Attachment is declared in `config/routing.yaml` under `routes.<task>.skills`, so
changing it is a config edit, not a code change.

Two skills are deliberately explicit-only, for the same reason. `api-integration`
applies when the problem *is* an integration, not whenever something is broken.
`outreach-writing` applies when the deliverable *is* copy — sourcing, list
hygiene and enrichment review are prospecting tasks that produce none, and a
writing procedure loaded for them is context spent making the model less
focused. `pfa leads draft` attaches it itself, so the one path that always
writes copy always has it.

`gdpr-compliance` is attached to `prospecting` because it passes the opposite
test: every task in that category touches personal data, by definition of what a
prospect list is.

## The shared rule

Every skill in this library inherits one rule from `fde-methodology`: **label
every claim** — FACT, HYPOTHESIS, CONCLUSION, ACTION TAKEN, ACTION RECOMMENDED —
and never promote a hypothesis to a fact because it is plausible or because time
is short. The skills differ in what they tell you to look at; they do not differ
in that.

## Commands

```bash
pfa skills                      # list the library
pfa skills show fde-methodology # print one skill in full
pfa skills validate             # check every skill parses and is well-formed
pfa hermes-config --write       # point Hermes at this directory
pfa run --skill api-integration "The client's webhook stopped arriving"
pfa run --skill outreach-writing "Rewrite this first message; it reads like a template"
```

## How these reach the agent

Hermes reads them **in place**. `pfa hermes-config --write` renders
`skills.external_dirs: [<abs path to this directory>]` into
`$HERMES_HOME/config.yaml`, so the agent loads the procedures from version
control and there is no copy to fall behind.

`pfa skills install` copies the library into `$HERMES_HOME/skills` instead, for
the case the config cannot cover — the agent running somewhere this repository
is not.

`pfa doctor` checks both routes, and checks the configured path actually
resolves here: Hermes silently skips an external directory that does not exist,
which would leave the agent running with no procedures and no error.

**Read-only matters.** An external skill directory is not a write-protection
boundary in Hermes; if the process can write here, the agent can rewrite its own
procedures. The compose stack mounts this directory read-only for that reason.

## Adding a skill

1. Create `skills/<category>/<name>/SKILL.md`. The directory name and the
   frontmatter `name` must match; validation enforces it.
2. Frontmatter requires `name`, `description` and `version` (`MAJOR.MINOR.PATCH`).
3. Write the body with the sections the existing skills use: **When to Use**, the
   non-negotiable rules, **Procedure**, **Output Template**, **Pitfalls**,
   **Verification**. The last one matters most — it is what the agent checks its
   own output against before delivering.
4. Run `pfa skills validate`, then `make test`.
5. To attach it to a task category, add its name to `routes.<task>.skills` in
   `config/routing.yaml`.

Keep it client-agnostic. Skills are committed to a public repository; a test
asserts no credential ever appears in one, and no client name or private detail
belongs in one either. The same test rejects any non-example hostname, so a
vendor's documentation URL does not belong in a procedure — put the concrete
endpoint in `config/mcp.yaml` and the citation in `docs/verified-facts.md`, and
keep the skill about the method.
