# Example Client

This directory is a fictional placeholder client used for development and testing.

**All data here is invented. Do not replace it with real client details.**

## What Goes Here

Each client directory contains:

- `config.yaml` — the client assistant config (business facts, services, tone,
  escalation contacts, retention settings, etc.)
- `leads/` — live lead JSONL files (**gitignored; never commit real leads**)
- `state/` — per-client runtime state (**gitignored**)

## Onboarding a New Client

Copy this directory, rename it to match the client slug (e.g.
`clients/smith-plumbing/`), and populate `config.yaml` from the schema defined
in `lead_hub/schemas/`.

Keep all real leads, secrets, and tokens out of git. See `docs/local-state.md`
for where operational data should live on the Mac mini.
