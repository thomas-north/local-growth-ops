# Plan 0008: Follow-up Scheduler and Weekly Client Report

GitHub issue: #8, "Implement follow-up scheduler and weekly client report"

## Goal

Add the next supervised ops layer after Telegram approval notifications. Identify
leads due for follow-up, generate safe operator-facing follow-up drafts, and
produce a plain-text weekly report. Nothing is ever sent automatically.

## Scope

Implement:

- Follow-up draft generation for due leads (existing list_due_followups storage
  helper already finds them)
- CLI command: `lead_hub.process_due_followups <client-slug> [--dry-run]`
- Weekly report CLI: `lead_hub.weekly_report <client-slug>`
- Respect max_followups from client config; clear next_followup_at when exhausted
- Skip leads in spam, escalated, closed, won, lost status for follow-up drafts
- Append-only audit logging for followup_draft_created events
- Tests for scheduler logic, exclusion rules, and weekly report output
- Update README.md, lead_hub/README.md, docs if needed

Defer:

- Interactive approval of follow-up drafts via Telegram buttons
- Sending follow-up messages to customers
- Email delivery of weekly report
- SQLite migration
- Cron setup (covered in plan 0009 runbook)

## Safety Requirements

- No automatic sends to leads
- No invented prices, availability promises, guarantees, or commitments in drafts
- Spam, escalated, closed, won, and lost leads must never receive follow-up drafts
- Every follow-up draft must have approval_required: True
- Weekly report avoids unnecessary PII (counts and short lead IDs; no raw emails
  or phone numbers in report output)
- No Telegram network calls in tests; no real state files written outside tmp_path

## Architecture

```
lead_hub/
  followup_scheduler.py    -- follow-up draft logic and workflow
  process_due_followups.py -- CLI entry point
  weekly_report.py         -- CLI entry point
```

### followup_scheduler.py

Key functions:

- EXCLUDED_STATUSES: frozenset of statuses that must never receive follow-up
  drafts (spam, escalated, closed, won, lost)

- count_followup_drafts(client_slug, lead_id) -> int
  Counts existing followup_draft_created audit events for a lead.
  Used to determine which follow-up number this is (1st, 2nd, etc.).

- compute_next_followup_at(config, followup_number) -> datetime | None
  Returns next follow-up datetime based on config cadence, or None if
  max_followups would be exceeded.

- build_followup_draft(lead, config, followup_number) -> DraftReply
  Builds a safe, template-based follow-up draft. No prices, no promises.
  approval_required always True.

- run_followup_workflow(lead, config, followup_count) -> AssistantRun
  Composes escalation check + skip classification + follow-up draft.
  Uses adapter "followup-dry-run-v1".

### process_due_followups.py

CLI: python3.11 -m lead_hub.process_due_followups <client-slug> [--dry-run]

Behaviour:
1. Validate client config.
2. Load due leads via list_due_followups(client_slug).
3. Skip any lead in EXCLUDED_STATUSES; log SKIP for each.
4. Count existing follow-up drafts for each lead.
5. If followup_count >= config.followup.max_followups: log SKIP (exhausted).
6. Run followup workflow -> AssistantRun.
7. Append AssistantRun to drafts.jsonl.
8. Append AuditEvent (kind=followup_draft_created) to audit.jsonl.
9. Compute next_followup_at (or None if max reached).
10. Update lead status to followup_scheduled; set new next_followup_at.
11. Print summary line per lead.

Exits 0 on success (including zero due), 1 on error, 2 on usage error.

### weekly_report.py

CLI: python3.11 -m lead_hub.weekly_report <client-slug>

Report sections:
- Report date and client name
- Lead summary by status (counts)
- Pending approvals (awaiting_approval) - lead IDs and names, no PII
- Follow-ups due now or overdue
- Escalations open
- Recommended operator actions (bullet list derived from state)
- Deferred (no email delivery, no Telegram send)

Exits 0 on success, 1 on error, 2 on usage error.

## Audit Event Extension

Add followup_draft_created to AuditEventKind in assistant_workflow.py.

## Status Transitions

Eligible input statuses for follow-up: replied, followup_scheduled
Output status after scheduling next: followup_scheduled (with updated next_followup_at)
Output status after final follow-up: followup_scheduled (next_followup_at=None,
so future list_due_followups calls will not return it again)

EXCLUDED_STATUSES = {spam, escalated, closed, won, lost}

## Follow-up Cadence (from config)

first_followup_days:   days from received_at to first follow-up (default 3)
second_followup_days:  days from received_at to second follow-up (default 7)
max_followups:         maximum follow-ups to generate (default 2)

next_followup_at for followup_number 1 = received_at + first_followup_days
next_followup_at for followup_number 2 = received_at + second_followup_days
followup_number >= max_followups: clear next_followup_at, no further drafts

## Tests

File: tests/test_followup.py

Required cases:

Scheduler logic:
- Genuine replied lead produces a follow-up draft
- Follow-up draft has approval_required=True
- Follow-up draft body contains no invented price
- Follow-up draft body does not promise availability
- Spam lead is excluded from follow-up
- Escalated lead is excluded
- Closed, won, lost leads are excluded
- count_followup_drafts returns 0 when no events exist
- count_followup_drafts returns correct count after audit events written
- compute_next_followup_at returns first_followup_days date for followup_number 0
- compute_next_followup_at returns second_followup_days date for followup_number 1
- compute_next_followup_at returns None when followup_number >= max_followups
- run_followup_workflow uses adapter followup-dry-run-v1
- Escalation check still fires for follow-up leads (complaint in message)

process_due_followups CLI:
- No args exits 2
- Missing client exits 1
- No due leads exits 0
- Due genuine lead gets draft written and status updated to followup_scheduled
- Excluded status lead is skipped
- Exhausted (max_followups reached) lead is skipped
- Audit event kind=followup_draft_created written per processed lead

weekly_report CLI:
- No args exits 2
- Missing client exits 1
- Empty state exits 0 and prints report header
- Counts by status are accurate
- Report does not include raw email or phone numbers
- Pending approvals section lists awaiting_approval leads
- Recommended actions section present

## Verification Commands

```bash
python3.11 --version
python3.11 -m pip install -e ".[dev]"
python3.11 -m pytest tests/
python3.11 -m compileall lead_hub openclaw tests -q
```

End-to-end dry-run:

```bash
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead example-client \
  --name "Followup Test" --email "ft@example.invalid" --service "eicr" \
  --message "Please quote for an EICR"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.list_due_followups example-client
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_due_followups \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.weekly_report example-client
```

Note: process_due_followups will show 0 due leads after process_new_leads because
the lead status is awaiting_approval (not replied/followup_scheduled). The unit
tests cover the scheduling path directly via manipulated state.

Stale-reference grep:

```bash
rg -n --pcre2 "python3(?!\.11)|python -m|state/<|config.example.yaml" \
  README.md docs lead_hub tests planning openclaw pyproject.toml
```

Safety grep:

```bash
rg -n "auto.?send|send_telegram_message\(|TELEGRAM_BOT_TOKEN\s*=|chat_id\s*=\"-?[0-9]|password|secret|token" \
  lead_hub tests README.md docs planning
```

## Documentation Updates

- README.md: add process_due_followups and weekly_report commands, update
  development status (plan 0008 complete)
- lead_hub/README.md: add command docs for process_due_followups and weekly_report,
  remove "Planned commands" stub for weekly_report
- docs/local-state.md: no new files needed; audit.jsonl already covers new events

## Tasks

- [x] Create planning/0008-follow-up-scheduler-weekly-report.md
- [x] Add followup_draft_created to AuditEventKind in assistant_workflow.py
- [x] Create lead_hub/followup_scheduler.py (draft logic, exclusion rules, workflow)
- [x] Create lead_hub/process_due_followups.py (CLI)
- [x] Create lead_hub/weekly_report.py (CLI)
- [x] Write tests in tests/test_followup.py
- [x] Update README.md (commands, development status)
- [x] Update lead_hub/README.md (commands, remove planned stub)
- [x] Run all verification commands
- [x] Update plan checkboxes and execution notes
- [x] Create branch codex/ops-followup-scheduler
- [x] Commit and open draft PR linked to issue #8

## Branch And PR

- [x] Branch: codex/ops-followup-scheduler
- [x] Draft PR linked to issue #8
- [x] PR description: scheduler design, exclusion rules, follow-up cadence,
  weekly report sections, deferred items, and verification commands run

## Execution Notes

**update_lead_status clear_next_followup_at flag:** The existing storage helper
treated next_followup_at=None as "don't change". This is correct for callers
that only update status, but process_due_followups needs to explicitly clear
next_followup_at when max_followups is reached. Added clear_next_followup_at=False
parameter to update_lead_status. When True, sets next_followup_at=None regardless
of the next_followup_at argument. All existing callers use the default (False) and
are unaffected.

**Followup cadence is relative to received_at:** compute_next_followup_at uses
lead.received_at as the anchor rather than "now", so the schedule is deterministic
and does not drift based on when the command runs. Example: if received_at is
2026-06-01 and first_followup_days=3, the first follow-up is always 2026-06-04
regardless of when process_due_followups runs.

**Operator marks replied manually:** No mark_replied CLI exists in this plan.
The operator sets status=replied and next_followup_at using update_lead_status
programmatically, or via a future command. The end-to-end test shows zero due
follow-ups after process_new_leads because the lead is in awaiting_approval, not
replied. Unit tests cover the scheduler path directly with pre-set lead state.

**Weekly report avoids PII:** Report output includes lead names (short identifier)
and short lead IDs but not raw email addresses or phone numbers. The test
test_report_does_not_contain_email verifies this.

**followup-dry-run-v1 adapter:** Consistent with dry-run-v1 naming from plan 0006.
Adapter string distinguishes follow-up runs from initial classification runs in
drafts.jsonl.

**Verification results:**
- python3.11 --version: 3.11.15 OK
- python3.11 -m pytest tests/: 335 passed (63 config + 42 storage + 39 intake + 75 prompts + 38 workflow + 35 telegram + 43 followup) OK
- python3.11 -m compileall lead_hub openclaw tests -q: clean OK
- End-to-end dry-run pipeline: manual_lead -> process_new_leads -> list_due_followups -> process_due_followups -> weekly_report all run without error OK
- Stale-reference grep: all matches are historical execution notes or grep commands OK
- Safety grep: all matches are documentation or test fixtures, no hardcoded secrets OK
