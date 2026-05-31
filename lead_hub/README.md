# lead_hub

Deterministic lead ingestion and state management for the follow-up assistant.

## Responsibility

This package owns:

- the normalised lead model (schema and validation)
- per-client JSONL lead storage
- lead status transitions
- helper commands for manual lead entry, status queries, and reports

## Planned Commands

These will be implemented in plans 0003 and 0004:

```bash
python -m lead_hub.validate_client example-client
python -m lead_hub.manual_lead example-client
python -m lead_hub.list_due_followups example-client
python -m lead_hub.weekly_report example-client
```

## Lead Status Flow

```
New
  → Needs reply draft
    → Awaiting approval
      → Replied
        → Follow-up scheduled
          → Won | Lost | Closed
  → Spam
  → Escalated
    → Closed
```

## Storage

MVP: one JSONL file per client at `/var/openclaw/clients/<client-slug>/leads.jsonl`
on the Mac mini. This path is outside this git repository and is never committed.

See `docs/local-state.md` for the full directory layout and alternative dev
paths.

## What Does Not Belong Here

- Openclaw prompt text → `openclaw/agents/followup-assistant/`
- Telegram approval logic → `openclaw/agents/followup-assistant/`
- Operator runbooks → `runbooks/`
