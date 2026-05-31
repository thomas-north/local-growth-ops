# Follow-Up Assistant — Openclaw Agent

This directory is the home of the Openclaw follow-up assistant's instructions,
prompts, and related configuration.

## Responsibility

This agent owns:

- lead classification (spam, genuine, out-of-scope, escalate)
- first reply drafting
- follow-up drafting
- escalation detection and flagging
- Telegram operator approval message formatting
- weekly lead report generation

## What Does Not Belong Here

- deterministic lead storage and status transitions → `lead_hub/`
- client config schema → `lead_hub/schemas/`
- operator setup procedures → `runbooks/`

## Planned Files

These will be added in plans 0005 and 0006:

```
instructions.md        — standing instructions the agent reads on every run
prompts/
  classify.md          — lead classification prompt
  draft_reply.md       — first reply draft prompt
  draft_followup.md    — follow-up draft prompt
  weekly_report.md     — weekly report prompt
  escalation.md        — escalation detection prompt
examples/
  classify_example.json
  draft_reply_example.json
```

## Rules The Agent Must Always Follow

- Do not send any message without operator approval in the MVP.
- Do not invent prices, timescales, guarantees, or availability.
- Do not handle complaints autonomously.
- Do not access a client's full inbox.
- Base every draft only on client config and lead content.
- Flag escalation triggers immediately.
- Keep drafts concise and in the client's configured tone.
