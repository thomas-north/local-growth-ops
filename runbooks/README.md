# Runbooks

Operator setup and production procedures for running the follow-up assistant
on the dedicated Mac mini.

## Runbooks

- [mac-mini-production.md](mac-mini-production.md) -- end-to-end production
  runbook: first-time setup, daily workflow, Telegram setup, Openclaw
  onboarding placeholder, cron scheduling, backup, log locations, reboot
  recovery, adding a client, pausing a client, daily/weekly checklists,
  and troubleshooting.

## Quick Reference

| Task | Command |
|------|---------|
| Validate config | `python3.11 -m lead_hub.validate_client <slug>` |
| Ingest website payload | `python3.11 -m lead_hub.ingest_website_payload <slug> payload.json` |
| Process new leads | `python3.11 -m lead_hub.process_new_leads <slug> --dry-run` |
| Send approval notifications | `python3.11 -m lead_hub.notify_approvals <slug>` |
| List due follow-ups | `python3.11 -m lead_hub.list_due_followups <slug>` |
| Process due follow-ups | `python3.11 -m lead_hub.process_due_followups <slug> --dry-run` |
| Weekly report | `python3.11 -m lead_hub.weekly_report <slug>` |
| List all leads | `python3.11 -m lead_hub.list_leads <slug>` |

All commands require `LOCAL_GROWTH_STATE_ROOT="/var/openclaw"` in production
and `source /var/openclaw/secrets/telegram.env` before live Telegram sends.

See [mac-mini-production.md](mac-mini-production.md) for the full runbook.
