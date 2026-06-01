# Plan 0004: Implement Intake Adapters For Website And Manual Leads

GitHub issue: #4, "Implement intake adapters for website form and manual leads"

## Goal

Create the deterministic intake layer that converts external lead payloads into
`NormalizedLead` records. This gives the future website form a stable contract
and keeps manual/operator-created leads separate from website-originated leads.

## Scope

Implement:

- website lead payload schema
- manual lead payload schema or shared manual adapter
- conversion functions from payloads to `NormalizedLead`
- command for ingesting a website payload JSON file
- command or refactor for ingesting manual payloads through the same adapter
- tests for valid and invalid intake payloads
- documentation of the website payload contract for `local-growth-sites`

Defer:

- actual website form UI
- webhook server
- Cloudflare Functions/Workers
- Openclaw classification or drafting
- Telegram approval workflow
- automatic follow-up scheduling
- real client data

## Design Decisions

- Use Python 3.11 commands explicitly.
- Use Pydantic v2 for payload schemas.
- Keep `NormalizedLead` as the canonical stored record.
- Website-originated leads must set `consent.privacy_accepted=true`.
- Manual/operator-created leads may set `consent.privacy_accepted=false`, but
  must use `source="manual"` and remain clearly test/operator initiated.
- Validate the client config before writing any lead.
- Use `LOCAL_GROWTH_STATE_ROOT` in tests and examples to avoid writing to
  `/var/openclaw/`.
- Do not implement network receiving in this plan. File-based JSON ingestion is
  enough for the contract.

## Website Payload Contract

Create a schema for a website form payload with these fields:

- `client_id`
- `site_id`
- `source_page`
- `submitted_at`
- `name`
- `preferred_contact_method`
- `email`
- `phone`
- `service_requested`
- `urgency`
- `message`
- `privacy_accepted`
- `marketing_opt_in`

Validation rules:

- `client_id` must match the configured client.
- `site_id`, `source_page`, `name`, and `message` must be non-empty strings.
- `submitted_at` must be a timezone-aware ISO datetime.
- At least one of `email` or `phone` must be present.
- `preferred_contact_method` must be one of `email`, `phone`, `sms`,
  `whatsapp`, or `unknown`.
- `urgency` must be one of `low`, `normal`, `high`, or `urgent`.
- `privacy_accepted` must be `true` for website payloads.
- `marketing_opt_in` defaults to `false` if absent.

Conversion behaviour:

- `source` on the stored lead should be `website:<site_id>`.
- `received_at` should come from `submitted_at`.
- `status` should be `new`.
- `next_followup_at` should be null.
- `conversation_summary` should be empty.
- `assigned_owner` should default to empty unless provided later by another
  workflow.

## Commands

Add:

- `python3.11 -m lead_hub.ingest_website_payload <client-slug> <payload.json>`
  - validates client config
  - validates payload
  - converts to `NormalizedLead`
  - appends to the client's JSONL store
  - prints the created lead ID

Update or refactor:

- `python3.11 -m lead_hub.manual_lead ...`
  - should use a shared manual adapter/factory path rather than building the
    `NormalizedLead` directly inside the CLI
  - existing command behaviour should remain compatible

## Tasks

- [x] Add `lead_hub/schemas/intake.py` or equivalent payload schema module.
- [x] Add website payload model.
- [x] Add manual payload model or shared manual adapter input model.
- [x] Add conversion function from website payload to `NormalizedLead`.
- [x] Add conversion function from manual payload to `NormalizedLead`.
- [x] Add `ingest_website_payload` command.
- [x] Refactor `manual_lead` to use the manual adapter.
- [x] Add fictional website payload fixture in tests.
- [x] Add tests for valid website payload ingestion.
- [x] Add tests rejecting website payloads with `privacy_accepted=false`.
- [x] Add tests rejecting client ID mismatch between command client and payload.
- [x] Add tests rejecting payloads with no contact method.
- [x] Add tests confirming manual lead command remains compatible.
- [x] Update README with the new ingestion command.
- [x] Update `lead_hub/README.md` with the website payload contract.
- [x] Add or update docs explaining the contract that `local-growth-sites` must
      later emit from its contact form.
- [x] Update this plan's checkboxes and execution notes as work completes.

## Verification

- [x] `python3.11 -m pip install -e ".[dev]"` succeeds.
- [x] Create a temp website payload JSON file and ingest it with
      `LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.ingest_website_payload example-client <payload.json>`.
- [x] With the same state root, `python3.11 -m lead_hub.list_leads example-client`
      shows the website lead.
- [x] A website payload with `privacy_accepted=false` exits non-zero.
- [x] A website payload whose `client_id` does not match the command client exits
      non-zero.
- [x] `LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.manual_lead example-client --name "Manual Lead" --email "manual@example.invalid" --message "Manual test"` still succeeds.
- [x] `python3.11 -m pytest tests/` succeeds (141 passed: 63 config + 42 storage + 36 intake).
- [x] `python3.11 -m compileall lead_hub openclaw tests -q` succeeds.
- [x] `rg -n --pcre2 "python3(?!\\.11)|python -m|state/<|config.example.yaml" README.md docs lead_hub tests planning pyproject.toml`
      returns no live stale command/path references except historical execution
      notes.
- [x] `git status --short` shows only intentional changes before commit.

## Branch And PR

- [x] Create a branch named `codex/ops-intake-adapters`.
- [x] Commit with a clear message.
- [x] Open a draft pull request linked to issue #4.
- [x] PR description includes payload contract decisions, files changed,
      deferred work, and verification commands run.

## Execution Notes

**`ManualLeadPayload.preferred_contact_method` defaulting:** The plan did not
specify a default for `preferred_contact_method` on the manual payload. Set it
to `ContactMethod.unknown`, matching the website payload default, so
`manual_payload_to_lead` always produces a valid `ContactInfo.preferred_method`.

**`manual_lead` refactored, contract preserved:** The CLI flags and output
format are unchanged. Internally, the command now builds a `ManualLeadPayload`
and calls `manual_payload_to_lead` instead of constructing `NormalizedLead`
fields directly. All existing `TestManualLeadCLI` tests in
`test_lead_storage.py` continue to pass.

**Post-review bug fix — `preferred_contact_method` regression (PR #15):**
The initial refactor passed only the contact values to `ManualLeadPayload`
without also passing `preferred_contact_method`, so all manual leads created
via the CLI stored `contact.preferred_method = unknown` regardless of which
flag was used. The pre-refactor CLI set this explicitly as
`ContactMethod.email if args.email else ContactMethod.phone`.
Fixed by computing `preferred` from the CLI args and passing it to the
payload before calling `manual_payload_to_lead`. Three regression tests added
to `TestManualLeadCLIBackwardCompat`: email-only → `email`, phone-only →
`phone`, both → `email` (tiebreak preserved from original code).
