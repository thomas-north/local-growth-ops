# Prompt: Escalation Detection

## Purpose

Determine whether a lead or conversation requires immediate operator
attention before any drafting or automated action takes place.

This prompt should be run as a pre-flight check on any lead before drafting
begins, and on any incoming message that updates a lead's status.

Bias toward escalation. The cost of a missed escalation is higher than the
cost of a false positive.

The client config and lead content are the source of truth.

---

## Input Context

You will be given:

- `client_config` — a JSON excerpt including `business`, `services`,
  `exclusions`, and `escalation_triggers`.
- `lead` — a JSON object: `lead_id`, `name`, `message`, `service_requested`,
  `urgency`, `status`, `conversation_summary`.

---

## Required Output

Return a single JSON object with exactly these fields:

```json
{
  "escalation_required": true | false,
  "severity": "<critical|high|medium|none>",
  "reasons": ["<reason>", "..."],
  "operator_summary": "<one paragraph for the operator explaining what was detected and why>",
  "suggested_operator_action": "<what the operator should do next>"
}
```

If `escalation_required` is `false`, `severity` must be `"none"`,
`reasons` must be an empty list, and `operator_summary` and
`suggested_operator_action` may be empty strings.

---

## Escalation Triggers

Always escalate for:

- Any complaint, dispute, or expression of dissatisfaction about past work
- A safety concern, urgent hazard, gas leak, electrical fault, or risk to life
- A request for a written guarantee, contract, or legal agreement
- A legal or insurance query
- An abusive, threatening, or distressing message
- Any indication of vulnerability (mental health crisis, bereavement, hardship)
- A refund or compensation request
- Work clearly outside the configured services listed in `exclusions`
- Any trigger listed in the client config `escalation_triggers`

Escalate for ambiguity — use `severity: "medium"` and `needs_human_review`
language rather than guessing.

---

## Severity Levels

| Severity | When |
|---|---|
| `critical` | Safety hazard, risk to life, abusive/threatening message |
| `high` | Complaint, legal/insurance query, refund request, vulnerability indicator |
| `medium` | Ambiguous escalation trigger, out-of-scope request, unusual message |
| `none` | No escalation triggers detected |

---

## Example

See `examples/escalation_input.json` and `examples/escalation_output.json`.
