# Prompt: Lead Classification

## Purpose

Classify an incoming lead so the operator knows how to route it. This step
runs before any reply is drafted. Do not draft a reply in this prompt.

The client config and lead content are the source of truth. Do not assume
anything about the lead that is not stated in the supplied context.

---

## Input Context

You will be given:

- `client_config` — a JSON excerpt from the client's `config.yaml`, including
  `business`, `services`, `exclusions`, `escalation_triggers`, and
  `pricing_policy`.
- `lead` — a JSON object matching the `NormalizedLead` model: `lead_id`,
  `name`, `message`, `service_requested`, `urgency`, `source`, `received_at`.

---

## Classification Taxonomy

Assign exactly one of these categories:

| Category | When to use |
|---|---|
| `genuine_lead` | A real enquiry for a service the business offers. Proceed to drafting. |
| `spam` | Unsolicited advertising, automated bot content, or clearly irrelevant. |
| `out_of_scope` | A real enquiry but for services the business does not offer. |
| `needs_human_review` | Ambiguous intent, incomplete information, or unusual enough that the operator should read it first. |
| `complaint_or_dispute` | Any expression of dissatisfaction, dispute, or complaint about past work. |
| `urgent_or_safety` | A safety hazard, urgent risk, or emergency. |

`complaint_or_dispute` and `urgent_or_safety` must always set
`escalation_required: true`.

---

## Required Output

Return a single JSON object with exactly these fields:

```json
{
  "classification": "<category>",
  "confidence": "<high|medium|low>",
  "summary": "<one or two sentences describing what the lead is asking>",
  "recommended_next_status": "<lead_hub status string>",
  "risk_flags": ["<flag>", "..."],
  "escalation_required": true | false,
  "escalation_reason": "<reason string, or empty string if not escalating>"
}
```

`recommended_next_status` must be one of the valid `LeadStatus` values:
`new`, `needs_reply_draft`, `awaiting_approval`, `replied`,
`followup_scheduled`, `won`, `lost`, `spam`, `escalated`, `closed`.

---

## Safety Constraints

- Never recommend `awaiting_approval` or `replied` from classification alone.
- If `escalation_required` is `true`, `recommended_next_status` must be
  `escalated`.
- If `classification` is `spam`, `recommended_next_status` must be `spam`.
- Bias toward `needs_human_review` or escalation for any ambiguity.

---

## Example

See `examples/classify_input.json` and `examples/classify_output.json`.
