# lead_hub

Deterministic lead ingestion and state management for the follow-up assistant.

## Responsibility

This package owns:

- the client assistant config schema and validation
- the normalised lead model (schema and validation)
- per-client JSONL lead storage
- lead status transitions
- helper commands for manual lead entry, status queries, and reports

## Schema

- Client assistant configs: `lead_hub.schemas.client_config` (Pydantic v2)
- Normalized lead model: `lead_hub.schemas.lead` (Pydantic v2)
- Intake payloads: `lead_hub.schemas.intake` — `WebsiteLeadPayload` and
  `ManualLeadPayload` with converters to `NormalizedLead`
- Workflow outputs: `lead_hub.schemas.assistant_workflow` — `EscalationCheck`,
  `LeadClassification`, `DraftReply`, `AssistantRun`, `AuditEvent`

See [docs/website-payload-contract.md](../docs/website-payload-contract.md)
for the full website payload schema shared with `local-growth-sites`.

## State Root

```
/var/openclaw/clients/<client-slug>/
  leads.jsonl     — normalized lead records
  drafts.jsonl    — AssistantRun records (classification + draft output)
  audit.jsonl     — AuditEvent records (append-only activity log)
```

Development: set `LOCAL_GROWTH_STATE_ROOT=<path>` to override.
State files are never committed to git. See `docs/local-state.md`.

## Commands

### Validate a client config

```bash
python3.11 -m lead_hub.validate_client <client-slug>
# OK: 'example-client' config is valid (Bright Spark Electrical, 5 service(s))
```

### Create a manual test lead

```bash
python3.11 -m lead_hub.manual_lead <client-slug> \
  --name "Test Lead" --email "lead@example.invalid" \
  --message "Please quote for an EICR" [--phone TEXT] [--service TEXT] [--urgency normal]
```

### List stored leads

```bash
python3.11 -m lead_hub.list_leads <client-slug>
```

### List due follow-ups

```bash
python3.11 -m lead_hub.list_due_followups <client-slug>
```

### Ingest a website form payload

```bash
python3.11 -m lead_hub.ingest_website_payload <client-slug> <payload.json>
```

Validates the client config, validates the JSON payload against
`WebsiteLeadPayload`, enforces `privacy_accepted=true` and client ID match,
then appends a `NormalizedLead` to the JSONL store.

### Process a single lead

```bash
python3.11 -m lead_hub.process_lead <client-slug> <lead-id> [--dry-run]
```

Classifies one lead, writes an `AssistantRun` to `drafts.jsonl` and an
`AuditEvent` to `audit.jsonl`, and updates lead status.

### Process all new leads

```bash
python3.11 -m lead_hub.process_new_leads <client-slug> [--dry-run]
```

Processes every lead in `new` status. Same storage outputs as above.

All commands: exit 0 on success, 1 on error, 2 on missing argument.

### Planned commands (plan 0008 onward)

```bash
python3.11 -m lead_hub.weekly_report example-client
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
