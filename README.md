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
    config.example.yaml     assistant config template
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

Bootstrap scaffold complete (plan 0001). Directory structure, example client
placeholder, `.gitignore` coverage, and local-state documentation are in place.

Remaining backlog:

2. Define the client assistant config schema.
3. Implement the lead hub storage model.
4. Add website and manual lead intake.
5. Openclaw prompts and agent instructions.
6. Lead classification and draft reply workflow.
7. Telegram operator approval workflow.
8. Follow-up scheduler and weekly client report.
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

## Future Commands

The expected command shape is:

```bash
python -m lead_hub.validate_client example-client
python -m lead_hub.manual_lead example-client
python -m lead_hub.list_due_followups example-client
python -m lead_hub.weekly_report example-client
```

These commands do not exist yet; they describe the target operator experience
for the first implementation pass.
