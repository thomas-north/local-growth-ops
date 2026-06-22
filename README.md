# local-growth-ops

Private operations workspace for the local business follow-up assistant.

This repository will contain the Openclaw-powered lead handling system for a
productized local business offer: a managed website plus supervised enquiry
follow-up. It is the private companion to `thomas-north/local-growth-sites`.

The goal is to let non-technical clients benefit from fast, reliable lead
responses without needing to install, configure, or understand Openclaw.

## Product Goal

Create a repeatable assistant model that can:

- ingest new leads from client websites
- classify enquiries
- draft first replies
- draft follow-ups
- escalate risky or sensitive conversations
- send operator approval messages
- produce weekly lead reports

The MVP is supervised. Openclaw drafts and schedules; a human approves before
anything sensitive or customer-facing is sent.

## Hosting Model

Openclaw will run centrally on the dedicated Mac mini.

Clients do not host this system. They interact through normal channels such as
email, Telegram, WhatsApp, or simple approval messages, depending on the package
we offer them.

Default model:

- client website sends leads into this ops system
- Openclaw monitors leads on a schedule
- Openclaw drafts replies and follow-ups
- the operator approves or escalates
- the client receives simple summaries and requests for approval

## Repository Structure

```
clients/
  example-client/           fictional placeholder client (config only — no real data)
    config.yaml             fictional assistant config (template for real clients)
lead_hub/                   deterministic lead ingestion and state scripts
  schemas/                  data models and validation (plan 0002 onward)
openclaw/
  agents/
    followup-assistant/     Openclaw agent instructions and prompts (plan 0005 onward)
runbooks/                   operator setup and Mac mini production procedures
tests/                      validation and workflow tests
docs/
  OVERALL_PLAN.md           phased implementation plan
  local-state.md            where live operational data lives outside git
planning/                   executable implementation plans (Codex writes, Claude Code executes)
```

Live lead state, logs, exports, and backups live **outside this repo** on the
Mac mini. See [docs/local-state.md](docs/local-state.md) for the directory
layout.

MVP storage is JSONL per client. SQLite can be introduced later if multi-client
reporting becomes awkward.

## Core Assistant Rules

The assistant must not:

- send unsupervised sales replies in the MVP
- invent prices
- handle complaints autonomously
- provide regulated advice
- make commitments about availability, refunds, guarantees, or outcomes
- access a client's full inbox during the first version

The assistant must:

- use client config as the source of truth
- escalate risky cases
- keep a concise audit trail
- minimize personal data in operator notifications
- support pausing a client
- keep real client data out of git

## Development Status

- Plan 0001 complete: bootstrap scaffold, directory structure, example client
  placeholder, `.gitignore` coverage, local-state documentation.
- Plan 0002 complete: Pydantic v2 client config schema, YAML loader,
  `validate_client` command, 62-test suite.
- Plan 0003 complete: normalized lead model, JSONL storage, status transitions,
  `manual_lead` / `list_leads` / `list_due_followups` commands, 42-test suite.
- Plan 0004 complete: website payload schema, manual adapter, `ingest_website_payload`
  command, refactored `manual_lead`, website contract docs, 36-test suite.
- Plan 0005 complete: Openclaw prompt library (instructions, 5 prompts, 10 JSON
  examples), 75-test validation suite.
- Plan 0006 complete: deterministic dry-run workflow, assistant schemas,
  draft/audit storage, `process_lead` / `process_new_leads` commands, 38-test suite.
- Plan 0007 complete: Telegram operator approval notification, `notify_approvals`
  command, PII-minimised message format, dry-run mode, 30-test suite.
- Plan 0008 complete: follow-up scheduler, `process_due_followups` command,
  `weekly_report` command, exclusion rules, 43-test suite.

Remaining backlog:
9. Mac mini production runbook.
10. Privacy, retention, and safety policy.
11. External-agent implementation brief.

See [docs/OVERALL_PLAN.md](docs/OVERALL_PLAN.md) for the full phased plan.

## Safety Rules

- Do not commit real leads.
- Do not commit client secrets, API tokens, Telegram tokens, inbox credentials,
  or webhook signing secrets.
- Keep example clients fictional.
- Keep live state, logs, exports, and backups out of git.
- Treat this repo as private operational infrastructure.

## Commands

This repo requires Python 3.11+. The system `python3` on the shared dev machine
is Python 3.9, so all commands use `python3.11` explicitly. On the Mac mini
production host, verify with `python3.11 --version` before running any command.

Install dependencies:

```bash
python3.11 -m pip install -e ".[dev]"
```

Validate a client config:

```bash
python3.11 -m lead_hub.validate_client example-client
```

Run tests:

```bash
python3.11 -m pytest tests/
```

Create a manual test lead:

```bash
LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.manual_lead example-client \
  --name "Test Lead" --email "lead@example.invalid" --message "Please quote for an EICR"
```

List stored leads:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.list_leads example-client
```

List due follow-ups:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.list_due_followups example-client
```

Ingest a website form payload:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.ingest_website_payload \
  example-client /path/to/payload.json
```

See [docs/website-payload-contract.md](docs/website-payload-contract.md) for
the full payload schema.

Process a single lead (dry-run classification + draft):

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.process_lead \
  example-client <lead-id> --dry-run
```

Process all new leads:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.process_new_leads \
  example-client --dry-run
```

Send operator approval notifications to Telegram (dry-run prints message, no network call):

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.notify_approvals \
  example-client --dry-run
```

Live mode requires env vars loaded from `/var/openclaw/secrets/telegram.env`:

```bash
source /var/openclaw/secrets/telegram.env
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.notify_approvals \
  example-client
```

Process due follow-ups (generates operator-review drafts for leads whose follow-up date has passed):

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.process_due_followups \
  example-client --dry-run
```

Generate a weekly operations report:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.weekly_report \
  example-client
```
