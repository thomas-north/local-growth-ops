# Privacy, Retention, and Safety Policy for Lead Handling

**Scope:** Openclaw-powered supervised lead follow-up MVP (local-growth-ops)
**Audience:** Operators managing the Mac mini production installation
**Status:** Operational controls document -- not legal advice

> This document describes the operational controls in place for the current
> MVP. It is not a substitute for legal advice. Before selling a lead-handling
> service more broadly or handling leads for clients in regulated sectors, have
> the data flows and retention practices reviewed by a qualified legal adviser
> (GDPR, UK data protection law, and any sector-specific rules may apply).

---

## 1. Overview

The system collects and processes limited personal data about prospective
customers (leads) on behalf of local service business clients. Every step
is operator-supervised: the assistant drafts; a human approves before
anything is sent to the customer or client.

The MVP principle is **minimum viable data**: collect only what is needed
to draft a useful response, store it securely outside git, retain it for
the configured period, and then delete or redact it.

---

## 2. Data Categories

### 2.1 Lead Identity and Contact Information

Collected when a lead submits a website enquiry form or is entered manually.

| Field | Source | Where stored |
|-------|--------|--------------|
| Name | Form / manual entry | leads.jsonl |
| Email | Form / manual entry | leads.jsonl |
| Phone (optional) | Form / manual entry | leads.jsonl |
| Service requested | Form / manual entry | leads.jsonl |
| Message content | Form / manual entry | leads.jsonl |
| Privacy accepted flag | Form | leads.jsonl |
| Urgency (optional) | Form / manual entry | leads.jsonl |
| Lead ID (UUID) | Generated | leads.jsonl |
| Received timestamp | Generated | leads.jsonl |

Contact information (email, phone) is personal data. It is stored only in
live JSONL files on the Mac mini and is never committed to git.

### 2.2 Assistant Drafts

When the assistant classifies a lead and generates a draft reply:

| Field | Source | Where stored |
|-------|--------|--------------|
| Classification result | Assistant | drafts.jsonl |
| Draft reply text | Assistant | drafts.jsonl |
| Risk flags | Assistant | drafts.jsonl |
| Run timestamp | Generated | drafts.jsonl |
| Adapter ID | Generated | drafts.jsonl |

Draft replies may contain the lead's name (from config) or a summary of
their request. They are operator-facing only -- no draft is sent to the
customer without human approval.

### 2.3 Audit Events

An audit event is written for every significant action (status change,
draft created, notification sent, escalation).

| Field | Source | Where stored |
|-------|--------|--------------|
| Lead ID | Reference | audit.jsonl |
| Event kind | System | audit.jsonl |
| Timestamp | Generated | audit.jsonl |
| Previous / new status | System | audit.jsonl |
| Run ID | Reference | audit.jsonl |

Audit events do not include raw contact information but do reference lead
IDs, which can be used to look up contact details in leads.jsonl.

### 2.4 Telegram Notifications

When the operator is notified about a lead pending approval, the Telegram
message includes:

- The lead's **name** (first field of NormalizedLead)
- A **300-character excerpt** from the lead's message (truncated)
- Lead ID (short prefix for operator reference)
- Classification and draft reply text

The system applies `redact_contact_details()` to the excerpt before
sending, which strips email addresses and phone numbers detected by regex.
However:

- The lead's name is included and cannot be redacted without losing utility.
- Long-form message content may contain additional PII not caught by regex
  (street addresses, dates of birth, account numbers, etc.).
- Telegram is a third-party service: their privacy policy and data
  retention apply to messages sent to Telegram servers.

**Operator action:** Do not include unnecessary PII in lead messages.
Treat Telegram notifications as operator-only communications and do not
forward them outside the approved operator group.

### 2.5 Weekly Reports

The weekly_report command produces a plain-text summary covering:

- Lead counts by status
- Pending approvals (lead ID and name, no email/phone)
- Due follow-ups (lead ID only)
- Open escalations
- Recommended operator actions

Reports are printed to stdout. They are not stored unless the operator
redirects the output to a file. If saved to `/var/openclaw/exports/`, they
fall under the export retention policy (section 4.4).

### 2.6 Exports

Operator-created exports (CSV, text) of lead data are written to
`/var/openclaw/exports/` on the Mac mini. These are outside git but may
contain identifiable information. Apply the retention limits in section 4.4.

### 2.7 Backups

Full backups of `/var/openclaw/` (including JSONL files) are stored in
`/var/openclaw/backups/`. See section 4.5 for backup retention.

---

## 3. Where Data Lives

```
In git (config only -- no personal data or secrets):
  clients/<slug>/config.yaml        -- client settings, fictional example only
  lead_hub/                         -- processing logic
  openclaw/                         -- agent prompts

Outside git (Mac mini /var/openclaw/):
  clients/<slug>/leads.jsonl        -- personal data -- NEVER commit
  clients/<slug>/drafts.jsonl       -- draft output -- NEVER commit
  clients/<slug>/audit.jsonl        -- audit trail -- NEVER commit
  clients/<slug>/state.json         -- run state -- NEVER commit
  logs/                             -- system logs -- NEVER commit
  exports/                          -- operator exports -- NEVER commit
  backups/                          -- backup archives -- NEVER commit
  secrets/telegram.env              -- credentials -- NEVER commit
  secrets/clients.env               -- webhook secrets -- NEVER commit
```

What must never be committed to git:
- Lead records (names, emails, phone numbers, message content)
- Assistant drafts or audit events referencing real leads
- Telegram bot tokens or chat IDs
- Webhook signing secrets or inbox credentials
- Production logs, exports, or backups
- Any file from /var/openclaw/

See `docs/local-state.md` for the canonical directory layout.

---

## 4. Retention

### 4.1 Configuration Fields

Retention is configured per client in `clients/<slug>/config.yaml`:

```yaml
retention:
  lead_retention_days: 365     # how long to keep full lead records
  delete_pii_after_days: 730   # how long before PII fields must be cleared
```

Constraints enforced by the schema validator:
- Both values must be positive integers.
- `delete_pii_after_days` must be >= `lead_retention_days`.

The example client defaults are 365 days for lead retention and 730 days
for PII deletion. Adjust these per client based on business need and any
applicable legal requirements.

### 4.2 Meaning of the Retention Fields

**lead_retention_days:** The lead record (including status, classification,
and follow-up schedule) should be kept for this many days after the lead was
received. After this period the full record may be deleted.

**delete_pii_after_days:** Even if the record is kept for business tracking
purposes, PII fields (name, email, phone, message content) must be cleared
or redacted after this many days.

In practice for the MVP, both actions (redaction and deletion) are performed
manually by the operator using the procedure in section 5.1. No automated
deletion script exists in the current version.

### 4.3 Audit Log Retention

Audit events in audit.jsonl do not contain raw PII but do reference lead
IDs. When a lead record is deleted, the corresponding audit events may be
kept for a longer period for operational integrity (troubleshooting, billing,
client reporting) or may be purged along with the lead. The operator should
decide per client what audit retention period applies and document it.

### 4.4 Export Retention

Exports in `/var/openclaw/exports/` should not be kept indefinitely.
Suggested policy: delete exports after 90 days or after they have been
delivered to the client, whichever comes first.

### 4.5 Backup Retention

Backups in `/var/openclaw/backups/` contain full copies of all JSONL files
including personal data. Suggested policy:
- Keep the last 4 weekly backups.
- Keep one monthly backup for 12 months.
- Delete older archives.

See `runbooks/mac-mini-production.md` Section 7 for the backup procedure.

---

## 5. Operator Procedures

### 5.1 Deleting or Redacting a Lead

No automated deletion tool exists in the current MVP. To delete or redact
a lead manually:

1. Identify the lead ID from `list_leads` output.
2. Open the relevant JSONL file (e.g. `/var/openclaw/clients/example-client/leads.jsonl`).
3. JSONL files are one JSON object per line. Each line is a version of the
   lead record (the last version with the matching `lead_id` is current).
4. To redact: replace name, email, phone, and message fields with empty
   strings or a placeholder such as `[redacted]`, and append the modified
   record as a new line so the audit trail shows the change was made.
5. To delete: remove all lines with the matching `lead_id` from all three
   JSONL files (leads.jsonl, drafts.jsonl, audit.jsonl) using a text editor
   or script.
6. Record the action in your operator log (outside git) with the date, lead
   ID, reason, and who performed the action.

> Take a backup before editing any JSONL file. JSONL files are append-only
> by design; manual edits should be treated as exceptional operations.

### 5.2 Handling a Subject Access or Deletion Request

If a lead contacts you requesting access to or deletion of their data:

1. Locate their records using `list_leads` and grep for their email.
2. For an access request: compile all lines in leads.jsonl, drafts.jsonl,
   and audit.jsonl that reference their lead ID. This is the full data held.
3. For a deletion request: follow the procedure in section 5.1 to remove
   or redact all records referencing their lead ID.
4. Check `/var/openclaw/exports/` for any exported files containing their
   data and delete those exports.
5. Check `/var/openclaw/backups/` -- backups may contain historical copies.
   Decide whether to delete or rotate the backup based on the request and
   legal advice.
6. If you sent a Telegram notification about this lead, be aware that the
   notification may persist in Telegram's servers. You cannot delete it
   from Telegram directly from this system.
7. Respond to the individual in writing confirming the action taken and the
   date.

### 5.3 Deleting Exports

To delete an export file:

```bash
rm /var/openclaw/exports/<filename>
```

Confirm the file is gone:

```bash
ls /var/openclaw/exports/
```

If a report was shared with a client (e.g. via email), inform the client
that the copy they received should also be deleted.

### 5.4 Backup Retention and Deletion

To list existing backups:

```bash
ls -lh /var/openclaw/backups/
```

To delete a backup archive:

```bash
rm /var/openclaw/backups/leads-YYYY-MM-DD.tar.gz
```

Keep the most recent 4 weekly backups and one per month for 12 months.
Delete older archives as part of the weekly operator checklist.

### 5.5 Pausing a Client

To pause a client (stop processing their leads):

1. Set `auto_send.first_reply: false` and `auto_send.followups: false` in
   their config -- these should already be false in the MVP.
2. Do not run `process_new_leads`, `process_due_followups`, or
   `notify_approvals` for the paused client.
3. Remove the client's cron entry or comment it out (do not delete the config
   or lead data while paused).
4. Notify the client that processing is paused.
5. To resume: re-add the cron entry and run the pipeline manually to process
   any leads that arrived during the pause period.

See also `runbooks/mac-mini-production.md` Section 11.

### 5.6 Incident Response: Data Sent to Wrong Place

If lead data (an approval notification, a report, or a JSONL export) is
accidentally sent to the wrong person or system:

1. **Contain:** Stop any further sends immediately. If a cron job is running,
   pause the client (section 5.5). If a Telegram message was sent to the
   wrong chat, remove it from the chat if you have permission.
2. **Assess:** Identify which leads and which data were exposed, and to whom.
   Check audit.jsonl for notification_sent events to see which leads were
   notified in the last run.
3. **Record:** Log the incident with timestamp, affected leads (by ID), data
   exposed, recipient, and how it was discovered. Keep this log outside git.
4. **Notify:** Depending on the severity and applicable law, you may be
   required to notify affected individuals and/or the ICO (UK) within 72
   hours. Get legal advice if unsure.
5. **Fix:** Correct the configuration or process that caused the error before
   resuming operations.
6. **Review:** After the incident, review whether any system change is needed
   to prevent recurrence.

---

## 6. Telegram PII Minimisation

The system applies two controls to limit personal data in Telegram messages:

**1. Field selection:** Notifications include only name, a 300-character
excerpt from the message, lead ID prefix, classification, and draft reply.
Email and phone are not included in the formatted message.

**2. Redaction regex:** The `redact_contact_details()` function strips email
addresses and phone numbers from the message excerpt before it is sent.

**Current limits of these controls:**
- Name is included and is not redacted.
- The excerpt may contain other PII (addresses, NI numbers, account details)
  not caught by the email/phone regex.
- Draft reply text may reference the lead's name or business context.
- Telegram messages are stored on Telegram's servers; deletion from this
  end is not possible after sending.

**Operator guidance:**
- Only approve Telegram bot access for operator accounts you control.
- Do not add external parties to the Telegram chat used for approvals.
- If a lead's message contains highly sensitive data (legal, medical,
  financial, or personal safety information), escalate manually rather than
  sending the standard Telegram notification.

---

## 7. Safety Escalation Rules

The system automatically escalates leads that match the client's configured
`escalation_triggers`. The default triggers for the example client are:

- complaint or dispute
- safety concern or urgent hazard
- request for written guarantee or contract
- legal or insurance query
- abusive or distressing message

When a lead is escalated:

- Its status is set to `escalated` in leads.jsonl.
- An audit event (`kind=escalated`) is written.
- An escalation note is included in the operator notification.
- No customer-facing reply is drafted automatically for escalated leads.
- The operator decides the next action manually.

**Operator guidance for common escalation scenarios:**

| Trigger | Action |
|---------|--------|
| Complaint or dispute | Do not draft a reply. Contact the client directly. |
| Safety concern or urgent hazard | Call the client or lead immediately if appropriate. Do not rely on email. |
| Legal or insurance query | Do not respond. Refer to the client's legal adviser or insurer. |
| Request for written guarantee | Do not draft a guarantee. Advise the client verbally. |
| Abusive or distressing message | Do not engage. Record the incident. Inform the client. |

Escalated leads remain in `escalated` status until the operator manually
changes the status to `closed` via `update_lead_status` (if implemented) or
a direct JSONL edit following section 5.1.

---

## 8. Human-Approval Policy

**No customer-facing message is sent without explicit operator approval.**

This is enforced at the schema level: `auto_send.first_reply` and
`auto_send.followups` must both be `false` in the MVP. The schema validator
rejects any config that sets either to `true`.

The approval workflow is:

1. `process_new_leads` or `process_due_followups` generates a draft reply.
2. `notify_approvals` sends the draft to the operator via Telegram for review.
3. The operator reads the draft and decides whether to send it, edit it, or
   discard it.
4. The operator sends the approved reply through the client's normal channel
   (email, phone, WhatsApp -- not automated by this system in the MVP).
5. The operator updates the lead status manually or through future tooling.

The weekly report is not sent to clients automatically. It is printed to
stdout for the operator's use.

---

## 9. Data Minimisation Checklist

The following checks should be performed before onboarding a new client:

- [ ] config.retention.lead_retention_days is set appropriately for the
      service type and any applicable legal requirements.
- [ ] config.retention.delete_pii_after_days is set >= lead_retention_days.
- [ ] config.auto_send.first_reply is false.
- [ ] config.auto_send.followups is false.
- [ ] Real approval contacts (Telegram chat ID) are set in secrets, not in
      config.yaml.
- [ ] The client has been informed that their customers' enquiries are
      processed by an AI assistant and reviewed by a human operator.
- [ ] The client's website privacy notice covers AI-assisted lead handling
      (get legal review).
- [ ] Backup schedule is in place and tested.
- [ ] Export and backup retention dates are documented.

---

## 10. Not Legal Advice

This document describes the operational controls that are currently in place.
It is written by the system operator, not a lawyer.

Before offering this service to clients in the UK or EU, or to clients in
regulated sectors (financial services, healthcare, legal), obtain legal advice
covering at minimum:

- UK GDPR / Data Protection Act 2018 obligations as a data processor
  (if the client is the controller) or as a data controller (if you hold
  data on your own account)
- Lawful basis for processing enquiry messages
- Data processing agreements with clients
- Third-party sub-processor obligations (Openclaw, Telegram)
- Subject access and erasure request obligations and timescales
- Breach notification obligations under Article 33 UK GDPR

---

*For directory layout see `docs/local-state.md`.*
*For backup and deletion procedures see `runbooks/mac-mini-production.md` Section 7.*
*For daily and weekly operator checklists see `runbooks/mac-mini-production.md` Section 12.*
