# Claude Code Instructions

You are the primary coding agent for this private operations repository. Codex
acts as product manager and planner by writing executable plans into
`planning/`.

## How To Work

1. Read `README.md`, `docs/OVERALL_PLAN.md`, and the latest relevant file in
   `planning/` before editing.
2. Execute the plan exactly unless it is technically impossible or unsafe.
3. Keep changes scoped to the current plan.
4. Update progress checkboxes in the plan as work is completed:
   - change `- [ ]` to `- [x]`
   - leave incomplete or intentionally deferred work unchecked
5. If you need to deviate from the plan, add a short note under the plan's
   `Execution Notes` section explaining why.
6. Do not commit real leads, client secrets, API tokens, Telegram tokens, inbox
   credentials, webhook secrets, or production logs.
7. Use fictional example clients only.
8. Run the verification commands listed in the plan.
9. Commit completed work on a branch and open a draft pull request unless the
   plan says otherwise.

## Documentation Consistency

When adding, renaming, or documenting a path, command, config file, state
location, or workflow, update every affected README, plan, and docs page in the
same PR.

Before marking a documentation-related task complete:

- search for the old name/path with `rg`
- confirm examples match the files actually created
- do not leave two competing "source of truth" locations for the same concept
- add an execution note if a planned name or location changed

## Config Identity Checks

When code loads a config by an external selector such as a client slug, folder
name, or command argument, the validated config's internal ID must match that
selector unless the plan explicitly says aliases are supported.

Before marking config loading complete:

- reject mismatches between path/argument IDs and internal config IDs
- add tests for the mismatch case
- make CLI success output use the requested ID and validated internal ID only
  when they are known to match

## Verification Commands

Verification commands in plans, READMEs, and PR descriptions must be
copy-paste-safe for the shared development machine and must satisfy any version
constraints declared by the repo.

Before marking verification complete:

- check the actual tool version used, e.g. `node --version`, `pnpm --version`,
  or `python3.11 --version`
- use the exact executable that satisfies the repo requirement
- if a generic command like `python3` or `node` depends on shell setup, document
  the setup or use the versioned executable instead
- do not claim a command passed if it only passes in a different local
  environment than the documented command
- apply this rule to READMEs, planning files, PR descriptions, code docstrings,
  CLI help/usage output, comments, and tests

## Repository Boundary

This repo owns private operations:

- client assistant configuration
- normalized lead storage
- lead intake adapters
- Openclaw agent prompts and instructions
- Telegram/operator approval workflows
- follow-up scheduling
- Mac mini runbooks
- privacy and retention policy

This repo does not own public website templates, Astro components, Cloudflare
Pages site code, or client website assets. Those belong in `local-growth-sites`.

## Planning Convention

Plans live in `planning/` and are numbered in execution order.

When asked to "work on the latest plan", choose the newest numbered plan that
still has unchecked required tasks.

Do not start future plans until the current plan's required tasks and
verification are complete, unless the prompt explicitly says to skip ahead.
