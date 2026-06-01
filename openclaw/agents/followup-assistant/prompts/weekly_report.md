# Prompt: Weekly Report

## Purpose

Summarise a client's lead activity over the past week. Produce two separate
text blocks: one for the operator (full detail) and one suitable to share
with the client (no unnecessary personal data).

The client config and supplied lead list are the source of truth.

---

## Input Context

You will be given:

- `client_config` — a JSON excerpt including `business`, `services`, and
  `tone`.
- `report_period` — `{ "from": "<ISO date>", "to": "<ISO date>" }`.
- `leads` — a JSON array of lead summaries for the period. Each entry
  includes `lead_id`, `name`, `service_requested`, `status`, `received_at`,
  `urgency`, `source`.

Do not include contact details (email, phone) in client-facing output.

---

## Required Output

Return a single JSON object with exactly these fields:

```json
{
  "report_title": "<string>",
  "period_summary": "<one or two sentences summarising overall activity>",
  "lead_counts": {
    "total": <integer>,
    "genuine_leads": <integer>,
    "spam": <integer>,
    "out_of_scope": <integer>,
    "escalated": <integer>,
    "won": <integer>,
    "lost": <integer>,
    "open": <integer>
  },
  "wins_or_likely_wins": [
    { "service": "<string>", "note": "<brief note, no personal data>" }
  ],
  "stale_leads": [
    { "lead_id_short": "<first 8 chars>", "service": "<string>", "last_status": "<string>", "days_since_update": <integer> }
  ],
  "recommended_actions": ["<action>", "..."],
  "client_facing_summary": "<plain-English paragraph suitable for sharing with the client, no contact details>",
  "operator_notes": "<full detail for the operator, including any concerns>"
}
```

---

## Rules

- Do not include lead names, email addresses, or phone numbers in
  `client_facing_summary`.
- Keep `client_facing_summary` positive in tone and focused on outcomes, not
  process.
- `operator_notes` may include lead-level detail (using short IDs, not full
  names or contact info).
- Do not fabricate activity. If a field has no data, use an empty list or
  zero count.
- Do not make performance claims or promises about future results.

---

## Example

See `examples/weekly_report_input.json` and
`examples/weekly_report_output.json`.
