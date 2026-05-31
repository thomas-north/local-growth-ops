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
