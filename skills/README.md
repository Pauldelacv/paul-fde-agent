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

Attachment is declared in `config/routing.yaml` under `routes.<task>.skills`, so
changing it is a config edit, not a code change. `api-integration` is
deliberately explicit-only: it applies when the problem is an integration, not
whenever something is broken. Attach it with `--skill api-integration`.

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
belongs in one either.
