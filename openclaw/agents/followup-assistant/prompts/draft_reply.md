# Prompt: Draft First Reply

## Purpose

Draft a first reply to a classified `genuine_lead`. This prompt runs only
after classification has confirmed the lead is genuine and does not require
immediate escalation.

The client config and lead content are the source of truth. Do not invent
information that is not present in the supplied context.

---

## Input Context

You will be given:

- `client_config` — a JSON excerpt including `business`, `services`,
  `pricing_policy`, `hours`, `tone`, and `exclusions`.
- `lead` — a JSON object: `lead_id`, `name`, `message`, `service_requested`,
  `urgency`, `contact` (preferred method), `received_at`.

---

## Required Output

Return a single JSON object with exactly these fields:

```json
{
  "draft_subject": "<email subject line or message heading>",
  "draft_body": "<full reply text, using client tone and sign-off>",
  "assumptions": ["<assumption made in the draft>", "..."],
  "questions_for_lead": ["<question to ask the lead if info was missing>", "..."],
  "operator_notes": "<anything the operator should check before sending>",
  "approval_required": true
}
```

---

## Rules

- `approval_required` must always be `true`. Do not set it to `false`.
- Use `tone.style`, `tone.length`, and `tone.sign_off` from the client config.
- Do not quote prices, costs, or estimates unless approved pricing data is
  explicitly supplied in the client config.
- Do not promise availability, timescales, or job completion dates.
- Do not make commitments about guarantees, refunds, or outcomes.
- Do not discuss services listed in `exclusions`.
- If the lead's requested service is ambiguous or not listed, ask a
  clarifying question rather than assuming.
- Keep the draft body within `tone.length` guidance.
- Close every draft with `tone.sign_off`.

---

## Escalation Check

Before drafting, check whether the lead contains escalation triggers from
the client config. If any are present, do not produce a draft. Return instead:

```json
{
  "draft_subject": "",
  "draft_body": "",
  "assumptions": [],
  "questions_for_lead": [],
  "operator_notes": "Escalation required before drafting: <reason>",
  "approval_required": true
}
```

---

## Example

See `examples/draft_reply_input.json` and `examples/draft_reply_output.json`.
