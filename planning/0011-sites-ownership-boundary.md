# Plan 0011: Clarify Website Ownership Boundary

## Goal

Keep future work in `local-growth-ops` focused on lead handling, with website
routes, page configuration, content collections, and site readiness checks
owned by `local-growth-sites`.

## Tasks

- [x] Clarify the website/operations boundary in `CLAUDE.md`.
- [x] Confirm this is an instruction-only change with no runtime impact.

## Verification

- [x] Review the updated Repository Boundary section for explicit ownership
      of route visibility, content collections, and content-completeness audits.
- [x] Confirm the worktree contains only the instruction and this plan.

## Execution Notes

- Updated the Ops Claude Code guidance to name page-visibility settings,
  content collections, and website content audits as Sites-owned concerns.
- No application code, schemas, lead payloads, or runtime behavior changed.
