# Follow-Up Assistant — Openclaw Agent

Supervised Openclaw agent for local business lead follow-up. Classifies
leads, drafts replies and follow-ups, detects escalations, and produces
weekly reports. **Every output requires operator approval before being sent.**

---

## Directory Structure

```
openclaw/agents/followup-assistant/
  README.md             this file
  instructions.md       standing rules loaded on every run
  prompts/
    classify.md         lead classification
    draft_reply.md      first reply drafting
    draft_followup.md   follow-up drafting
    escalation.md       escalation detection (pre-flight check)
    weekly_report.md    weekly activity summary
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

---

## How It Works

1. **Escalation check** — run `escalation.md` on any incoming lead or updated
   message before any other action. If `escalation_required: true`, stop and
   notify the operator. No draft is produced.

2. **Classification** — run `classify.md` on genuine (non-escalated) leads.
   The output includes a `recommended_next_status` to update the lead hub.

3. **Draft reply** — run `draft_reply.md` for leads classified as
   `genuine_lead`. The draft is held for operator approval.

4. **Draft follow-up** — run `draft_followup.md` for leads where
   `next_followup_at` has passed. Respects `followup.max_followups`.

5. **Weekly report** — run `weekly_report.md` on a weekly schedule. Produces
   both operator and client-facing summaries.

All outputs are structured JSON matching the required fields in each prompt.
No output is sent to a lead or client without human approval.

---

## Prompt Inputs

Each prompt expects a `client_config` excerpt (from the validated
`clients/<slug>/config.yaml`) and lead or lead-list context. See the
individual prompt files and example JSON files for exact structure.

---

## Safety Rules

The assistant must not:

- send anything without operator approval
- invent prices, timescales, guarantees, or availability
- handle complaints autonomously
- provide regulated advice
- access data outside the supplied context

See `instructions.md` for the full rule set.

---

## Example Data

All examples use the fictional `example-client` (Bright Spark Electrical,
South Leeds). No real client data, phone numbers, or email addresses appear
in this directory.

---

## What Does Not Belong Here

- Deterministic lead storage → `lead_hub/`
- Client config schema → `lead_hub/schemas/`
- Operator runbooks → `runbooks/`
- Live secrets or tokens → `/var/openclaw/secrets/` (outside git)
