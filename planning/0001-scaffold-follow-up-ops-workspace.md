# Plan 0001: Scaffold Follow-Up Assistant Ops Workspace

GitHub issue: #1, "Scaffold follow-up assistant ops workspace"

## Goal

Create the initial private operations workspace structure for the follow-up
assistant product. This is a bootstrap task only. Do not build the full lead
hub, assistant workflow, or Telegram approval flow yet.

## Scope

Implement:

- a clear repo structure for future client configs, lead hub code, Openclaw
  prompts, runbooks, tests, and local state examples
- fictional example client placeholders
- safety-focused ignore rules for operational data
- enough documentation that the next plan can implement client config schema

Defer:

- full client assistant config schema
- normalized lead model
- intake adapters
- Openclaw prompt implementation
- Telegram integration
- cron production setup

## Tasks

- [x] Create `clients/example-client/` with fictional placeholder content only.
- [x] Create `lead_hub/` for future deterministic ingestion and state scripts.
- [x] Create `openclaw/agents/followup-assistant/` for future agent instructions
      and prompts.
- [x] Create `runbooks/` for operator setup and production procedures.
- [x] Create `tests/` for future validation and workflow tests.
- [x] Create a local-state placeholder directory or documentation explaining
      where state/logs should live outside git.
- [x] Update `.gitignore` to exclude state, logs, secrets, exports, backups,
      local environment files, and live lead data.
- [x] Update `README.md` if actual structure differs from the current
      documentation.
- [x] Keep all example data fictional and commit no secrets.

## Verification

- [x] Confirm no real client data, secrets, lead logs, or tokens are present.
- [x] `git status --short` shows only intentional changes before commit.
- [x] Any lightweight tests or checks introduced by this plan pass.

## Branch And PR

- [x] Create a branch named `codex/ops-scaffold`.
- [x] Commit with a clear message.
- [x] Open a draft pull request linked to issue #1.
- [x] PR description includes what was scaffolded, what was deferred, and any
      verification performed.

## Execution Notes

Add notes here if implementation requires a meaningful deviation from the plan.
