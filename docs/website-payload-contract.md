# Website Lead Payload Contract

This document is the canonical reference for the JSON payload that
`local-growth-sites` must emit from its contact form and that
`local-growth-ops` ingests via `lead_hub.ingest_website_payload`.

## Schema

The payload must be a JSON object with the following fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `client_id` | string | yes | Must match the configured client slug |
| `site_id` | string | yes | Identifies the specific site instance |
| `source_page` | string | yes | Path of the page that submitted the form, e.g. `/contact` |
| `submitted_at` | string (ISO 8601) | yes | Timezone-aware datetime, e.g. `2026-06-01T10:30:00+00:00` |
| `name` | string | yes | Lead's full name |
| `preferred_contact_method` | string | no | One of `email`, `phone`, `sms`, `whatsapp`, `unknown` (default: `unknown`) |
| `email` | string | yes* | *At least one of `email` or `phone` must be present |
| `phone` | string | yes* | *At least one of `email` or `phone` must be present |
| `service_requested` | string | no | Service slug or label, e.g. `eicr` |
| `urgency` | string | no | One of `low`, `normal`, `high`, `urgent` (default: `normal`) |
| `message` | string | yes | The lead's enquiry message |
| `privacy_accepted` | boolean | yes | **Must be `true`**. Website forms must not submit without consent. |
| `marketing_opt_in` | boolean | no | Defaults to `false` if absent |

## Constraints

- `privacy_accepted` must be `true`. Payloads with `false` are rejected.
- `submitted_at` must include a timezone offset (UTC or local). Naive
  datetimes are rejected.
- `client_id` in the payload must match the client slug used when calling
  `ingest_website_payload`. Mismatches are rejected.
- At least one contact method (`email` or `phone`) must be provided.

## Conversion to NormalizedLead

When ingested, the payload is converted as follows:

| Payload field | Stored as |
|---|---|
| `client_id` | `lead.client_id` |
| `"website:" + site_id` | `lead.source` |
| `submitted_at` | `lead.received_at` |
| `name` | `lead.name` |
| `email` / `phone` / `preferred_contact_method` | `lead.contact.*` |
| `message` | `lead.message` |
| `service_requested` | `lead.service_requested` |
| `urgency` | `lead.urgency` |
| `privacy_accepted` / `marketing_opt_in` | `lead.consent.*` |
| *(auto)* | `lead.lead_id` (UUID4) |
| *(auto)* `"new"` | `lead.status` |
| *(auto)* `null` | `lead.next_followup_at` |
| *(auto)* `""` | `lead.assigned_owner` |
| *(auto)* `""` | `lead.conversation_summary` |

## Example Payload

```json
{
  "client_id": "example-client",
  "site_id": "example-client-main",
  "source_page": "/contact",
  "submitted_at": "2026-06-01T10:30:00+00:00",
  "name": "Jane Smith",
  "preferred_contact_method": "email",
  "email": "jane@example.invalid",
  "phone": null,
  "service_requested": "eicr",
  "urgency": "normal",
  "message": "I need a landlord electrical certificate for my property in South Leeds. When are you available?",
  "privacy_accepted": true,
  "marketing_opt_in": false
}
```

See `tests/fixtures/website_payload_valid.json` for a working example.

## Ingestion Command

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.ingest_website_payload \
  example-client /path/to/payload.json
```

In the MVP, payloads arrive as files (e.g. written by a webhook shim or
passed manually). A webhook receiver will be added in a later plan once
the contact form is live.
