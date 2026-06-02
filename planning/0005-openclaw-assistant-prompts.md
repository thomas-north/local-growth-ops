# Plan 0005: Create Openclaw Assistant Prompts And Instructions

GitHub issue: #5, "Create Openclaw follow-up assistant prompts and agent instructions"

## Goal

Create the reusable Openclaw instruction layer for the supervised local-business
follow-up assistant.

This plan should give Openclaw enough written structure to classify incoming
leads, draft first replies, draft follow-ups, detect escalations, and produce
weekly summaries while keeping the MVP human-approved and safe.

This plan does not need to run Openclaw end-to-end yet. It creates the prompt
library, examples, and tests/docs that later workflow scripts will call.

## Scope

Implement prompt and instruction artifacts under:

`openclaw/agents/followup-assistant/`

Required modules:

- standing assistant instructions
- lead classification prompt
- first reply drafting prompt
- follow-up drafting prompt
- escalation detection prompt
- weekly reporting prompt
- example inputs and outputs for each major prompt
- lightweight validation tests for required files, safety language, and example
  structure

Defer:

- running Openclaw automatically
- lead status mutation from prompt outputs
- Telegram approval messages
- actual model/API calls
- cron/launchd scheduling
- production secrets
- client inbox integration

## Product Position

The assistant is a supervised operator tool.

It may:

- classify a lead
- summarize what the lead is asking for
- draft a reply in the client's tone
- draft a follow-up
- flag risks and escalation reasons
- prepare weekly report text

It must not:

- send anything without human approval
- invent prices, availability, guarantees, refunds, or commitments
- handle complaints autonomously
- provide regulated advice
- access or summarize a client's full inbox in the MVP
- use data outside the client config and supplied lead/conversation context

## Required Directory Shape

Create or update this structure:

```text
openclaw/agents/followup-assistant/
  README.md
  instructions.md
  prompts/
    classify.md
    draft_reply.md
    draft_followup.md
    escalation.md
    weekly_report.md
  examples/
    classify_input.json
    classify_output.json
    draft_reply_input.json
    draft_reply_output.json
    draft_followup_input.json
    draft_followup_output.json
    escalation_input.json
    escalation_output.json
    weekly_report_input.json
    weekly_report_output.json
```

If a different file layout is clearly better, document the deviation in
Execution Notes and update all README references.

## Prompt Design Requirements

All prompt files should be operational, not fluffy. Each should include:

- purpose
- expected input context
- required output shape
- safety constraints
- escalation rules where relevant
- concise example guidance or references to example files

Prefer structured JSON output for prompts that will be consumed by deterministic
scripts later. JSON examples must be valid JSON.

### Classification Prompt

Classify leads into a small, documented taxonomy.

Required categories:

- `genuine_lead`
- `spam`
- `out_of_scope`
- `needs_human_review`
- `complaint_or_dispute`
- `urgent_or_safety`

Required output fields:

- `classification`
- `confidence`
- `summary`
- `recommended_next_status`
- `risk_flags`
- `escalation_required`
- `escalation_reason`

### Draft Reply Prompt

Draft a first reply for a genuine lead.

Required output fields:

- `draft_subject`
- `draft_body`
- `assumptions`
- `questions_for_lead`
- `operator_notes`
- `approval_required`

Rules:

- `approval_required` must always be true in the MVP.
- Use client config tone and sign-off.
- Do not quote prices unless explicit approved pricing data is supplied.
- Do not promise times, availability, guarantees, or outcomes.

### Draft Follow-Up Prompt

Draft a follow-up for a lead that has not responded.

Required output fields:

- `draft_body`
- `followup_number`
- `operator_notes`
- `approval_required`
- `should_stop_followups`

Rules:

- Respect client `followup.max_followups`.
- Keep follow-ups short and polite.
- Stop or escalate when the conversation suggests complaint, distress, safety,
  opt-out, or out-of-scope work.

### Escalation Prompt

Detect cases that should not receive autonomous drafting.

Required output fields:

- `escalation_required`
- `severity`
- `reasons`
- `operator_summary`
- `suggested_operator_action`

Rules:

- Bias toward escalation for ambiguity in the MVP.
- Escalate complaints, disputes, safety concerns, legal/insurance questions,
  abusive/distressed messages, urgent hazards, refunds, guarantees, and requests
  outside the configured services.

### Weekly Report Prompt

Summarize client lead activity for a weekly operator/client report.

Required output fields:

- `report_title`
- `period_summary`
- `lead_counts`
- `wins_or_likely_wins`
- `stale_leads`
- `recommended_actions`
- `client_facing_summary`
- `operator_notes`

Rules:

- Do not include unnecessary personal data in client-facing summaries.
- Keep operator notes separate from client-facing text.

## Example Data Requirements

Examples must use the fictional `example-client` config style only. Do not add
real leads, real phone numbers, real email addresses, or real client data.

Each input example should include enough context for the prompt to make a
decision:

- client config excerpt
- lead excerpt or lead list
- relevant conversation/follow-up state, where applicable

Each output example should match the prompt's required output fields exactly.

## Tests And Validation

Add tests under `tests/` that check:

- all required prompt files exist
- all required example JSON files exist
- every example JSON file parses
- output examples contain the required keys
- safety-critical phrases are present in `instructions.md` or prompt files:
  - no unsupervised sending in MVP
  - do not invent prices
  - do not promise availability/timescales
  - escalate complaints/disputes/safety concerns
  - approval required
- prompt docs mention that client config and lead content are the source of
  truth

Keep tests deterministic and local. Do not call Openclaw, OpenAI, the network,
Telegram, or any external service.

## Documentation Updates

- Update `openclaw/agents/followup-assistant/README.md` so it reflects the
  actual files created.
- Update top-level `README.md` development status to mark plan 0005 complete
  when done.
- Update `docs/OVERALL_PLAN.md` only if the phase boundary changes.
- Update this plan's checkboxes and execution notes.

## Tasks

- [x] Review current `openclaw/agents/followup-assistant/README.md`.
- [x] Create or update `instructions.md` with standing assistant rules.
- [x] Create `prompts/classify.md`.
- [x] Create `prompts/draft_reply.md`.
- [x] Create `prompts/draft_followup.md`.
- [x] Create `prompts/escalation.md`.
- [x] Create `prompts/weekly_report.md`.
- [x] Create valid JSON input/output examples for classification.
- [x] Create valid JSON input/output examples for first reply drafting.
- [x] Create valid JSON input/output examples for follow-up drafting.
- [x] Create valid JSON input/output examples for escalation detection.
- [x] Create valid JSON input/output examples for weekly reporting.
- [x] Add deterministic tests for file existence, JSON validity, output keys,
      and safety language.
- [x] Update README/docs to describe the prompt library.
- [x] Update this plan's checkboxes and execution notes.

## Verification

- [x] `python3.11 --version` satisfies `pyproject.toml` (3.11.15).
- [x] `python3.11 -m pip install -e ".[dev]"` succeeds.
- [x] `python3.11 -m pytest tests/` succeeds (219 passed: 63 config + 42 storage + 39 intake + 75 prompt library).
- [x] `python3.11 -m compileall lead_hub openclaw tests -q` succeeds.
- [x] `find openclaw/agents/followup-assistant -maxdepth 3 -type f | sort`
      shows the expected prompt and example files (17 files).
- [x] `python3.11 -m json.tool` succeeds for every `examples/*.json` file (10/10 OK).
- [x] `rg -n --pcre2 "python3(?!\\.11)|python -m|state/<|config.example.yaml" README.md docs lead_hub tests planning openclaw pyproject.toml`
      returns no unapproved stale command/path references (all matches are
      historical execution notes or the plan's own verification text).
- [x] `rg -n "real client|actual client|@gmail|@hotmail|07[0-9]{9}|\\+44" openclaw/agents/followup-assistant`
      returns no real-client-looking example data (the two matches are warning
      statements in README.md and instructions.md that say "No real client data"
      — see execution notes).
- [x] `git status --short` shows only intentional changes before commit.

## Branch And PR

- [x] Create a branch named `codex/ops-openclaw-prompts`.
- [x] Commit with a clear message.
- [x] Open a draft pull request linked to issue #5.
- [x] PR description includes prompt design decisions, examples added, deferred
      work, and verification commands run.

## Execution Notes

**Safety phrase case sensitivity:** The test suite searched for safety phrases
using exact case (`phrase in content`). Two phrases from `SAFETY_PHRASES` —
`"invent prices"` and `"source of truth"` — appear in `instructions.md` as
title-case headings ("**Invent prices.**", "## Source Of Truth"). The intent of
the tests is to confirm the concepts are present, not a specific capitalisation.
Fixed by lower-casing both sides of the comparison (`content.lower()`). No
content change needed in the prompt files.

**Post-review README backlog fix:** The plan-0005 commit introduced a backlog
regression: item 5 ("Openclaw prompts and agent instructions") was not removed
from the remaining backlog, and item 6 appeared twice. Fixed in a follow-up
commit: removed the completed item 5 and the duplicate item 6, leaving a clean
ordered list starting at 6.

**Real-client grep false positives:** The verification grep for real-client data
returns two matches, both from warning statements in documentation:
- `openclaw/agents/followup-assistant/README.md`: "No real client data, phone
  numbers, or email addresses appear in this directory."
- `openclaw/agents/followup-assistant/instructions.md`: "No real client data,
  real phone numbers, real email addresses, or real personal information should
  ever appear in this repository."
These are the correct negative-assertion statements required by the plan.
No actual real-client data is present.
