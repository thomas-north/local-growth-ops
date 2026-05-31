# Plan 0002: Define Client Assistant Config Schema

GitHub issue: #2, "Define client assistant config schema"

## Goal

Turn `clients/example-client/config.yaml` from an informal placeholder into a
validated assistant configuration contract. This schema becomes the source of
truth for future lead classification, reply drafting, escalation rules, and
follow-up scheduling.

## Scope

Implement:

- Python project metadata and dependency setup for schema validation
- a Pydantic-based client assistant config schema
- YAML loading for `clients/<client-slug>/config.yaml`
- a validation command for client configs
- tests for valid and invalid config examples
- documentation updates for the new command and schema location

Defer:

- normalized lead model
- lead JSONL storage
- website form intake
- Openclaw prompt rendering
- Telegram sending or approval handling
- real client onboarding

## Design Decisions

- Use Python 3.11+.
- Use Pydantic v2 for schema validation.
- Use PyYAML for reading `config.yaml`.
- Add `pyproject.toml` with project dependencies and a `dev` optional dependency
  group for pytest.
- Keep the canonical client config path as `clients/<client-slug>/config.yaml`.
- Keep live lead state outside git at `/var/openclaw/`; do not create runtime
  state in this plan.
- Keep approval contact values non-secret. If a value would expose a real chat
  ID, token, inbox credential, or webhook secret, represent it as an empty
  optional field or documented secret reference.

## Required Schema Behaviour

The schema must validate the current fictional example client and should reject
obviously unsafe or malformed configs.

Required top-level fields:

- `client_id`
- `client_slug`
- `business`
- `services`
- `exclusions`
- `pricing_policy`
- `hours`
- `tone`
- `approval`
- `escalation_triggers`
- `followup`
- `auto_send`
- `retention`

Validation rules:

- `client_id` and `client_slug` must be non-empty slugs using lowercase letters,
  numbers, and hyphens only.
- `client_id` and `client_slug` must match for now.
- `business.name`, `business.legal_name`, `business.description`,
  `business.phone`, `business.email`, and `business.area` are required.
- `business.email` must be a valid email address. Example domains are allowed.
- `business.address_visible` must be boolean.
- `services` must contain at least one service.
- Each service must have a non-empty `name` and slug-formatted `slug`.
- Service slugs must be unique.
- `exclusions` and `escalation_triggers` must each contain at least one entry.
- `pricing_policy` must be non-empty.
- `hours` must include `monday_friday`, `saturday`, and `sunday`.
- `tone.style`, `tone.length`, and `tone.sign_off` are required.
- `approval.telegram_chat_id` and `approval.email` are optional strings. Empty
  strings are allowed for the example client because real values may live in
  secrets.
- `followup.first_followup_days` and `followup.second_followup_days` must be
  positive integers.
- `followup.second_followup_days` must be greater than or equal to
  `followup.first_followup_days`.
- `followup.max_followups` must be between 0 and 5.
- `auto_send.first_reply`, `auto_send.followups`, and `auto_send.weekly_report`
  must be booleans.
- MVP safety rule: `auto_send.first_reply` and `auto_send.followups` must be
  `false`. Reject configs that set either to `true`.
- `retention.lead_retention_days` and `retention.delete_pii_after_days` must be
  positive integers.
- `retention.delete_pii_after_days` must be greater than or equal to
  `retention.lead_retention_days`.

## Tasks

- [ ] Add `pyproject.toml` with package metadata, runtime dependencies, and
      pytest dev dependency.
- [ ] Add a schema module, e.g. `lead_hub/schemas/client_config.py`.
- [ ] Add a loader/validator module for `clients/<slug>/config.yaml`.
- [ ] Add a command module so this works:
      `python3 -m lead_hub.validate_client example-client`.
- [ ] Ensure the command exits non-zero and prints useful errors for invalid
      configs.
- [ ] Update `clients/example-client/config.yaml` only if required by the schema,
      keeping all data fictional.
- [ ] Add tests for the valid example config.
- [ ] Add tests for representative invalid configs:
      - missing required field
      - invalid slug
      - duplicate service slug
      - unsafe auto-send enabled
      - invalid follow-up ordering
- [ ] Update README docs with the actual install/test/validation commands.
- [ ] Update `lead_hub/README.md` to point to the new schema and validation
      command.
- [ ] Update this plan's checkboxes and execution notes as work completes.

## Verification

- [ ] `python3 -m pip install -e ".[dev]"` succeeds.
- [ ] `python3 -m lead_hub.validate_client example-client` succeeds.
- [ ] `python3 -m pytest tests/` succeeds.
- [ ] `python3 -m compileall lead_hub openclaw tests` succeeds.
- [ ] `rg -n "config.example.yaml|state/<" README.md docs lead_hub clients planning`
      returns no stale source-of-truth references except historical execution
      notes that explicitly describe prior fixes.
- [ ] `git status --short` shows only intentional changes before commit.

## Branch And PR

- [ ] Create a branch named `codex/ops-client-config-schema`.
- [ ] Commit with a clear message.
- [ ] Open a draft pull request linked to issue #2.
- [ ] PR description includes schema decisions, files changed, deferred work, and
      verification commands run.

## Execution Notes

Add notes here if implementation requires a meaningful deviation from the plan.
