# Plan 0010: Privacy, Retention, and Safety Policy for Lead Handling

GitHub issue: #10, "Create privacy, retention, and safety policy for lead handling"

## Goal

Document the operational privacy, retention, and safety controls for the
supervised lead handling MVP. This is a practical operator guide -- not legal
boilerplate -- covering how personal data is minimised, stored, retained,
exported, backed up, and deleted under the current system architecture.

## Scope

Produce one policy document:

  docs/privacy-retention-safety.md

Covering:
- Data categories handled by the system
- Where data lives (repo vs live state) and what must never be committed
- Retention defaults derived from config.retention fields
- Operator procedures: delete/redact a lead, delete exports, backup
  retention, subject access/deletion requests, pause a client,
  incident response
- Telegram PII minimisation and limits
- Safety escalation rules (matching escalation_triggers in config)
- Human-approval policy (no customer-facing sends without operator approval)
- "Not legal advice" note and recommendation for legal review

Update the following if useful:
- README.md: add privacy policy pointer
- docs/local-state.md: reference privacy policy for retention guidance
- runbooks/mac-mini-production.md: cross-reference privacy doc in
  troubleshooting/incident section
- lead_hub/README.md: note privacy doc for data handling
- CLAUDE.md: no change required (repo boundary already covers this)

Do not add:
- deletion code or scripts (documentation-only plan)
- real client data, tokens, chat IDs, or secrets anywhere
- legal compliance claims

## Safety Notes

- No real client data, real lead data, real tokens, or secrets.
- No network calls.
- All examples use fictional slugs and data.
- Do not claim legal compliance; describe operational controls only.

## Verification Commands

```bash
python3.11 --version
python3.11 -m pytest tests/
python3.11 -m compileall lead_hub openclaw tests -q
```

End-to-end dry-run:

```bash
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead example-client \
  --name "Policy Test" --email "policy@example.invalid" --service "eicr" \
  --message "Please quote for an EICR"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.notify_approvals \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.weekly_report example-client
```

Stale-reference grep:

```bash
rg -n --pcre2 "python3(?!\.11)|python -m|state/<|config.example.yaml" \
  README.md docs lead_hub tests planning openclaw pyproject.toml runbooks
```

Safety grep:

```bash
rg -n "TELEGRAM_BOT_TOKEN\s*=|chat_id\s*=\s*\"-?[0-9]|password|secret|token|api[_-]?key|private key|real client|real lead" \
  README.md docs lead_hub tests planning openclaw runbooks
```

## Tasks

- [x] Create planning/0010-privacy-retention-safety-policy.md
- [x] Write docs/privacy-retention-safety.md
- [x] Update README.md (add privacy policy pointer)
- [x] Update docs/local-state.md (cross-reference privacy policy for retention)
- [x] Update runbooks/mac-mini-production.md (incident response cross-reference)
- [x] Update lead_hub/README.md (data handling note)
- [x] Run all verification commands
- [x] Update plan checkboxes and execution notes
- [x] Create branch codex/ops-privacy-policy
- [x] Commit and open draft PR linked to issue #10

## Branch And PR

- [x] Branch: codex/ops-privacy-policy
- [x] Draft PR linked to issue #10
- [x] PR description: policy sections covered, data categories, retention
  defaults, operator procedures, Telegram PII minimisation, escalation rules,
  human-approval policy, not-legal-advice note, and verification commands run

## Execution Notes

- docs/privacy-retention-safety.md written with 10 sections: Overview, Data
  Categories (6 sub-sections), Where Data Lives, Retention (5 sub-sections),
  Operator Procedures (6 sub-sections), Telegram PII Minimisation, Safety
  Escalation Rules, Human-Approval Policy, Data Minimisation Checklist, Not
  Legal Advice.
- No deletion code added; this is a documentation-only plan as scoped.
- runbooks/mac-mini-production.md: added "Data Sent to the Wrong Place"
  troubleshooting entry cross-referencing the privacy doc incident procedure.
- docs/local-state.md: added Retention section cross-referencing privacy doc.
- lead_hub/README.md: added Data Handling section cross-referencing privacy doc.
- README.md: added privacy-retention-safety.md to repo structure, updated
  development status (plan 0010 complete), reduced remaining backlog to item 11.
- Verification: python3.11 3.11.15, pytest 336 passed, compileall clean,
  end-to-end dry-run passed, stale-reference grep clean, safety grep clean
  (all matches are documentation, planning patterns, or test fixtures with
  .invalid domains -- no hardcoded secrets).
