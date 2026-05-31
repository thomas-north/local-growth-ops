# Plan 0003: Implement Lead Hub Storage And Normalized Lead Model

GitHub issue: #3, "Implement lead hub storage and normalized lead model"

## Goal

Create the deterministic lead model and JSONL storage layer that future intake
adapters and Openclaw workflows will use. This is the foundation for recording,
querying, and updating leads without storing operational state in git.

## Scope

Implement:

- Pydantic normalized lead schema
- lead status enum
- JSONL append/read helpers under the canonical `/var/openclaw/` runtime root
- status transition/update helpers
- commands for creating manual test leads, listing leads, and listing due
  follow-ups
- tests for validation, storage, status updates, and due follow-up filtering
- docs updates for the new commands and runtime state behaviour

Defer:

- website form intake adapter
- Openclaw classification or drafting
- Telegram approval workflow
- automatic scheduled runs
- weekly reports
- real client data

## Design Decisions

- Use Python 3.11 commands explicitly.
- Use Pydantic v2, matching the client config schema.
- Use JSONL as MVP storage.
- Use `/var/openclaw/clients/<client-slug>/leads.jsonl` as the canonical
  production path.
- Support an environment variable override named `LOCAL_GROWTH_STATE_ROOT` for
  tests and local development.
- Tests must never write to `/var/openclaw/`; they must use a temporary state
  root.
- Keep writes append-friendly and simple, but it is acceptable for this MVP to
  rewrite the per-client JSONL file when updating a lead status.
- Do not commit live lead data.

## Normalized Lead Model

Required fields:

- `lead_id`
- `client_id`
- `source`
- `name`
- `contact`
- `message`
- `service_requested`
- `urgency`
- `consent`
- `received_at`
- `status`
- `next_followup_at`
- `assigned_owner`
- `conversation_summary`

Suggested nested fields:

- `contact.email`
- `contact.phone`
- `contact.preferred_method`
- `consent.privacy_accepted`
- `consent.marketing_opt_in`

Status enum values:

- `new`
- `needs_reply_draft`
- `awaiting_approval`
- `replied`
- `followup_scheduled`
- `won`
- `lost`
- `spam`
- `escalated`
- `closed`

Validation rules:

- `lead_id` and `client_id` must be non-empty slugs or slug-like IDs.
- `source`, `name`, and `message` must be non-empty strings.
- At least one of `contact.email` or `contact.phone` must be present.
- `contact.preferred_method` must be one of `email`, `phone`, `sms`,
  `whatsapp`, or `unknown`.
- `urgency` must be one of `low`, `normal`, `high`, or `urgent`.
- `received_at` and `next_followup_at`, when present, must be timezone-aware ISO
  datetimes.
- `next_followup_at` may be null.
- `assigned_owner` and `conversation_summary` may be empty strings.
- `consent.privacy_accepted` must be true for non-manual production leads, but
  manual test leads may set a clearly documented test value. If this rule is too
  early for implementation, document the chosen MVP behaviour in execution
  notes and tests.

## Commands

Add these commands:

- `python3.11 -m lead_hub.manual_lead example-client`
  - creates a fictional/manual test lead with safe defaults
  - supports optional flags for name, email, phone, service, message, urgency
- `python3.11 -m lead_hub.list_leads example-client`
  - lists stored leads in a concise table or line format
- `python3.11 -m lead_hub.list_due_followups example-client`
  - lists leads with `next_followup_at` due at or before now

Keep command output plain and operator-friendly. Do not add Openclaw model calls
in this plan.

## Tasks

- [x] Add `lead_hub/schemas/lead.py` with the normalized lead schema and status
      enum.
- [x] Add storage helpers for resolving state root, client directory, and
      `leads.jsonl`.
- [x] Add JSONL read/write helpers.
- [x] Add a helper to create a lead with generated `lead_id` and current
      timezone-aware `received_at`.
- [x] Add a helper to update lead status and optional follow-up timestamp.
- [x] Add a helper to list due follow-ups.
- [x] Add `manual_lead` command.
- [x] Add `list_leads` command.
- [x] Add `list_due_followups` command.
- [x] Ensure commands validate the client config before operating.
- [x] Ensure tests use `LOCAL_GROWTH_STATE_ROOT` or injectable temporary state
      roots and never write to `/var/openclaw/`.
- [x] Add tests for valid lead creation and serialization.
- [x] Add tests for invalid lead validation.
- [x] Add tests for JSONL round-trip storage.
- [x] Add tests for status update.
- [x] Add tests for due follow-up filtering.
- [x] Update README docs with the new commands.
- [x] Update `lead_hub/README.md` with the lead model, storage location, state
      root override, and command examples.
- [x] Update `docs/local-state.md` if needed.
- [x] Update this plan's checkboxes and execution notes as work completes.

## Verification

- [x] `python3.11 -m pip install -e ".[dev]"` succeeds.
- [x] `LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.manual_lead example-client --name "Test Lead" --email "lead@example.invalid" --message "Please quote for an EICR"` succeeds.
- [x] `LOCAL_GROWTH_STATE_ROOT="<same temp dir>" python3.11 -m lead_hub.list_leads example-client` shows the created lead.
- [x] `LOCAL_GROWTH_STATE_ROOT="<same temp dir>" python3.11 -m lead_hub.list_due_followups example-client` runs successfully.
- [x] `python3.11 -m pytest tests/` succeeds (104 passed: 62 config + 42 storage).
- [x] `python3.11 -m compileall lead_hub openclaw tests -q` succeeds.
- [x] `rg -n --pcre2 "python3(?!\\.11)|python -m|state/<|config.example.yaml" README.md docs lead_hub tests planning pyproject.toml`
      returns no live stale command/path references except historical execution
      notes.
- [x] `git status --short` shows only intentional changes before commit.

## Branch And PR

- [x] Create a branch named `codex/ops-lead-hub-storage`.
- [x] Commit with a clear message.
- [x] Open a draft pull request linked to issue #3.
- [x] PR description includes model decisions, files changed, deferred work, and
      verification commands run.

## Execution Notes

**`consent.privacy_accepted` for manual leads:** The plan notes this rule may be
too early for MVP implementation. Manual test leads set `privacy_accepted=False`
and this is explicitly accepted — the model does not enforce `True` at the schema
level. The docstring and a dedicated test document this. Production intake
(plan 0004) will enforce `True` for website-originated leads.

**`list_leads` command:** The plan specified `list_leads` as a command name but
listed it under section "Commands" only. Implemented as
`python3.11 -m lead_hub.list_leads` alongside `manual_lead` and
`list_due_followups`.

**`docs/local-state.md` unchanged:** No updates were needed — the file already
correctly documents the `/var/openclaw/` root and the `LOCAL_GROWTH_STATE_ROOT`
override is documented in `lead_hub/README.md` and `lead_hub/storage.py`.
