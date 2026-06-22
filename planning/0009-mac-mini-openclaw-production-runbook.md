# Plan 0009: Mac Mini Openclaw Production Runbook

GitHub issue: #9, "Document Mac mini Openclaw production runbook"

## Goal

Create a practical, repeatable operator runbook for running this system on the
dedicated Mac mini. A fresh operator must be able to follow it to verify
readiness, run the daily workflow, add a client, and recover from a reboot.

## Scope

Produce one consolidated runbook:

  runbooks/mac-mini-production.md

Covering:

- Machine prerequisites and Python 3.11 install
- Repository checkout and dependency install
- State root directory layout and permissions
- Secrets file setup (format only -- no real values in git)
- Config validation
- Full workflow pipeline: ingest -> classify -> notify -> follow-up -> report
- Openclaw onboarding section (placeholder -- credentials not assumed present)
- Telegram env var setup and verification
- Log locations and how to tail them
- Backup procedure
- Cron scheduling pattern (read-only: classify and notify steps only, never auto-send)
- Reboot recovery steps
- How to add a new client
- How to pause and resume a client
- Daily and weekly operator checklist
- Troubleshooting for common failures

Update:
- runbooks/README.md: replace planned stubs with actual file references
- README.md: add runbooks pointer and update development status
- docs/local-state.md: add reference to backup-procedure section now in runbook

Do not add:
- launchd plists that send customer messages automatically
- real credentials, tokens, chat IDs, or client data anywhere
- code changes to lead_hub or tests (documentation-only plan)

## Runbook Structure

```
runbooks/mac-mini-production.md
  1. Prerequisites
  2. First-time Setup
     2.1 Repository checkout
     2.2 Python 3.11 install (Homebrew)
     2.3 State root directory
     2.4 Secrets files
     2.5 Dependency install
     2.6 Config validation
     2.7 Smoke test (dry-run)
  3. Daily Workflow
     3.1 Source secrets
     3.2 Process new leads
     3.3 Send approval notifications
     3.4 Process due follow-ups
     3.5 Weekly report
  4. Telegram Setup and Verification
  5. Openclaw Onboarding (future)
  6. Cron Scheduling
  7. Backup Procedure
  8. Log Locations
  9. Reboot Recovery
  10. Adding a New Client
  11. Pausing and Resuming a Client
  12. Daily and Weekly Checklists
  13. Troubleshooting
```

## Safety Notes

- No launchd plists that send customer messages automatically (violates MVP
  supervised posture).
- Cron section documents classify/notify commands only; operator approves before
  any reply is sent.
- Secrets section shows the ENV VAR format only, with placeholder values.
- All example client slugs are fictional (example-client).

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
  --name "Runbook Test" --email "rb@example.invalid" --service "eicr" \
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
rg -n "TELEGRAM_BOT_TOKEN\s*=|chat_id\s*=\"-?[0-9]|password|secret|token|api[_-]?key|private key" \
  README.md docs lead_hub tests planning openclaw runbooks
```

## Tasks

- [x] Create planning/0009-mac-mini-openclaw-production-runbook.md
- [x] Write runbooks/mac-mini-production.md
- [x] Update runbooks/README.md (replace stubs with actual file references)
- [x] Update README.md (add runbooks pointer, update development status)
- [x] Update docs/local-state.md (add backup runbook reference)
- [x] Run all verification commands
- [x] Update plan checkboxes and execution notes
- [x] Create branch codex/ops-mac-mini-runbook
- [x] Commit and open draft PR linked to issue #9

## Branch And PR

- [x] Branch: codex/ops-mac-mini-runbook
- [x] Draft PR linked to issue #9
- [x] PR description: runbook sections, Openclaw onboarding placeholder,
  secrets file format, cron safety posture, and verification commands run

## Execution Notes

- runbooks/mac-mini-production.md written with 13 sections covering all scope items.
- Openclaw onboarding section (section 5) left as placeholder pending Openclaw
  gateway credentials; noted clearly in the runbook.
- Cron section documents classify/notify pipeline only; no launchd that auto-sends.
- Secrets section uses placeholder values only (your-bot-token-here, <token>).
- All example slugs use fictional example-client.
- docs/local-state.md stale reference ("runbooks/backup-procedure.md to be written
  in plan 0009") updated to point to mac-mini-production.md Section 7.
- runbooks/README.md replaced planned stubs with actual file references and added
  quick-reference command table.
- README.md updated: development status, repository structure, remaining backlog.
- Verification: python3.11 --version (3.11.15), pytest 336 passed, compileall
  clean, end-to-end dry-run passed, stale-reference grep clean, safety grep clean
  (all matches are placeholder formats or documentation -- no hardcoded secrets).
