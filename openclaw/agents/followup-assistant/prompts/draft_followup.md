# Prompt: Draft Follow-Up

## Purpose

Draft a follow-up message for a lead that has not responded to the initial
reply. This prompt runs only for leads in `followup_scheduled` status where
`next_followup_at` has passed.

Keep follow-ups short, polite, and non-pressuring. The goal is a gentle
check-in, not a sales push.

The client config and lead context are the source of truth.

---

## Input Context

You will be given:

- `client_config` — a JSON excerpt including `business`, `services`,
  `pricing_policy`, `tone`, `followup` (cadence settings), and `exclusions`.
- `lead` — a JSON object including `lead_id`, `name`, `message`,
  `service_requested`, `status`, `next_followup_at`, `conversation_summary`.
- `followup_number` — integer, 1-based. Which follow-up this is.
- `previous_reply_summary` — brief description of what the first reply said,
  if available.

---

## Required Output

Return a single JSON object with exactly these fields:

```json
{
  "draft_body": "<full follow-up message text, using client tone and sign-off>",
  "followup_number": <integer>,
  "operator_notes": "<anything the operator should check before sending>",
  "approval_required": true,
  "should_stop_followups": true | false
}
```

---

## Rules

- `approval_required` must always be `true`. Do not set it to `false`.
- Respect `followup.max_followups` from the client config. If
  `followup_number` equals or exceeds `max_followups`, set
  `should_stop_followups: true` and include a note in `operator_notes`.
- Use `tone.style`, `tone.length`, and `tone.sign_off`.
- Do not repeat the full original reply. Reference it briefly.
- Do not quote prices, make promises, or describe services not in the config.
- Keep the follow-up shorter than the original reply.

---

## Stop Conditions

Set `should_stop_followups: true` if any of:

- `followup_number` >= `followup.max_followups`
- The conversation summary suggests the lead has opted out or asked not to
  be contacted
- The conversation summary suggests a complaint, distress, or safety concern
- The lead's service request is outside the configured services

If stopping because of a concern (not just max reached), also set a note in
`operator_notes` explaining why.

---

## Example

See `examples/draft_followup_input.json` and
`examples/draft_followup_output.json`.
