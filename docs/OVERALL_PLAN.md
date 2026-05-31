# Overall Plan: Follow-Up Assistant Operations

## Summary

Build a private Openclaw-powered operations system for supervised local business
lead follow-up.

The first sellable service is a managed website plus enquiry assistant. The
website captures leads; this repo stores and processes them; Openclaw drafts
responses and follow-ups; humans approve or escalate.

Clients should not need technical skills. They should not need GitHub,
Cloudflare, Openclaw, command-line tools, or direct access to operational state.

## Repository Boundary

This repo is responsible for:

- client assistant configuration
- normalized lead storage
- lead intake adapters
- Openclaw prompts and agent instructions
- classification and draft reply workflows
- Telegram/operator approval workflow
- follow-up scheduling
- weekly reporting
- Mac mini production runbooks
- privacy, retention, and safety policy

This repo is not responsible for:

- public website templates
- Astro components
- Cloudflare Pages site code
- public client website assets
- client handover repositories

Those website concerns belong in `local-growth-sites`.

## Implementation Phases

### Phase 1: Bootstrap

- Create the private ops workspace structure.
- Add fictional example client data.
- Add `.gitignore` coverage for state, logs, secrets, exports, and backups.
- Document repo safety rules.

Definition of done:

- A new operator understands what belongs in the repo.
- No real client data or secrets are present.
- Future components have clear directories.

### Phase 2: Client Assistant Config

- Define a validated per-client assistant config.
- Include business facts, services, exclusions, pricing policy, tone, hours,
  approval contacts, escalation contacts, follow-up cadence, auto-send settings,
  and retention settings.
- Default auto-send permission to `none`.

Definition of done:

- The fictional example client validates.
- Unsafe or malformed config fails clearly.
- Another operator can onboard a new client from the example.

### Phase 3: Lead Hub

- Define the normalized lead model.
- Store MVP lead state in per-client JSONL files.
- Add commands/helpers to create leads, update status, list open leads, and list
  due follow-ups.

Lead statuses:

- New
- Needs reply draft
- Awaiting approval
- Replied
- Follow-up scheduled
- Won
- Lost
- Spam
- Escalated
- Closed

Definition of done:

- A manual test lead can be created.
- A lead can move through expected statuses.
- Malformed records fail validation.

### Phase 4: Intake Adapters

- Add an adapter for the `local-growth-sites` contact form payload.
- Add manual lead entry for pilots and testing.
- Keep client ID validation strict.

Definition of done:

- A sample website payload becomes a normalized lead.
- A manual lead can be created from a command.
- Invalid client IDs fail clearly.

### Phase 5: Openclaw Assistant Layer

- Create reusable Openclaw instructions and prompts.
- Cover lead classification, first reply drafting, follow-up drafting,
  escalation detection, and weekly reporting.
- Keep deterministic lead handling in scripts and judgment-oriented drafting in
  Openclaw.

Definition of done:

- Prompts include examples.
- The assistant knows what it must never do.
- Drafts are based only on client config and lead content.

### Phase 6: Approval And Follow-Up

- Create Telegram operator approval messages.
- Include lead summary, classification, draft reply, risk flags, and suggested
  action.
- Add follow-up scheduling for valid unreplied leads.
- Generate weekly client reports.

Definition of done:

- A test lead produces an approval-ready draft.
- Spam, complaints, and out-of-scope requests are handled safely.
- Weekly reports summarize useful operator actions.

### Phase 7: Production Runbook

- Document Mac mini setup.
- Include Openclaw gateway startup, Telegram checks, cron checks, secrets audit,
  backups, reboot recovery, and client pause/resume.

Definition of done:

- The Mac mini can be verified as ready for production operation.
- Gateway health is explicit.
- The operator has daily and weekly checklists.

## Initial GitHub Issue Order

1. Scaffold follow-up assistant ops workspace.
2. Define client assistant config schema.
3. Implement lead hub storage and normalized lead model.
4. Implement intake adapters for website form and manual leads.
5. Create Openclaw follow-up assistant prompts and agent instructions.
6. Build lead classification and draft reply workflow.
7. Implement Telegram operator approval workflow.
8. Implement follow-up scheduler and weekly client report.
9. Document Mac mini Openclaw production runbook.
10. Create privacy, retention, and safety policy for lead handling.
11. Create external-agent implementation brief.

## Assumptions

- Openclaw runs centrally on the dedicated Mac mini.
- Telegram is the first operator notification channel.
- The MVP is supervised and draft-first.
- Clients are non-technical.
- Real client inbox integrations are postponed until after website-form intake
  works reliably.
- JSONL storage is sufficient for the first pilots.
- This repo remains private.
