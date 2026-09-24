# Privacy, Retention, and Safety Policy for Lead Handling

**Scope:** Supervised lead follow-up MVP (local-growth-ops)
**Audience:** Operators managing the Mac mini production installation
**Status:** Operational controls document -- not legal advice

> This document describes the operational controls in place for the current
> MVP. It is not a substitute for legal advice. Before selling a lead-handling
> service more broadly or handling leads for clients in regulated sectors, have
> the data flows and retention practices reviewed by a qualified legal adviser
> (GDPR, UK data protection law, and any sector-specific rules may apply).

---

## 1. Overview

The system is designed to process personal data about prospective customers
(leads) on behalf of local service business clients. The repository validates
website payloads supplied as local JSON files and supports manual lead entry;
it does not currently expose a live website intake endpoint. After ingestion,
the workflow uses a deterministic local adapter and does not call OpenClaw or
an external model provider. Telegram approval notifications can be sent when
explicitly run in live mode. Every customer-facing reply remains a manual,
operator-approved action.

The OpenClaw prompts are present, but a live model adapter is not implemented.
Before enabling one with real lead data, document the model provider, data sent,
provider retention and access terms, and any required client disclosures in
this policy and the relevant client arrangements.

The MVP principle is **minimum viable data**: collect only what is needed
to draft a useful response, store it securely outside git, track the configured
retention targets manually, and then delete or redact it. The software does not
enforce those targets.

---

## 2. Data Categories

### 2.1 Lead Identity and Contact Information

Website payload fields are collected when an operator ingests a form payload
JSON file; other leads may be entered manually. The intake tool does not delete
the input JSON file after ingestion, so the operator must secure and remove that
copy according to the applicable retention decision.

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
| Source, status, requested service, follow-up time, owner, conversation summary | Form / operator / workflow | leads.jsonl |

Contact information (email, phone) is personal data. After ingestion, it is
stored in live JSONL files on the Mac mini and must never be committed to git.
The source payload file may remain at its original path until the operator
removes it.

### 2.2 Assistant Drafts

When the local workflow classifies a lead and generates a draft reply, it writes
an `AssistantRun` to `drafts.jsonl`:

| Field | Source | Where stored |
|-------|--------|--------------|
| Classification result and summary | Local workflow | drafts.jsonl |
| Draft reply text, assumptions, questions, operator notes | Local workflow | drafts.jsonl |
| Risk flags and escalation details | Local workflow | drafts.jsonl |
| Run timestamp | Generated | drafts.jsonl |
| Adapter ID | Generated | drafts.jsonl |

Draft replies and classifications may contain the lead's name or details from
their request. These records are personal-data-bearing even when generated
locally. They are operator-facing only; no draft is sent to the customer by
this system.

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

The current audit-event builders do not copy the lead's contact fields or
message into `detail`, but events reference lead IDs that can be linked to
contact details in `leads.jsonl`. Treat the audit file as personal-data-bearing
for access, retention, and deletion decisions. Review any future adapter that
changes what is written to `detail`. The `notification_sent` event kind is also
used when `notify_approvals --dry-run` prints a notification locally; inspect
its `detail` before treating it as proof of a Telegram send.

### 2.4 Telegram Notifications

When the operator is notified about a lead pending approval in live mode, the
Telegram message currently includes:

- Client/business name and the lead's **name**
- A **300-character excerpt** from the lead's message (truncated)
- Lead ID (short prefix), classification, confidence, and summary
- Escalation flags/details when present
- The complete draft subject and body, assumptions, questions, and operator notes

The system applies `redact_contact_details()` to the original lead-message
excerpt only, stripping email addresses and phone numbers detected by regex.
It does not redact the draft, classification, business name, or lead name.
However:

- The lead's name is included and is not redacted by the formatter.
- Long-form message content may contain additional PII not caught by regex
  (street addresses, dates of birth, account numbers, etc.).
- Telegram is a third-party service: their privacy policy and data
  retention apply to messages sent to Telegram servers.

**Operator action:** Do not include unnecessary PII in lead messages.
Treat Telegram notifications as operator-only communications and do not
forward them outside the approved operator group.

### 2.5 Weekly Reports

The `weekly_report` command produces a plain-text summary covering:

- Lead counts by status
- Pending approvals (lead ID and name, no email/phone)
- Due follow-ups (lead ID, name, and due date)
- Open escalations
- Recommended operator actions

Reports are printed to stdout. They are not stored unless the operator
redirects the output to a file. If saved to `/var/openclaw/exports/`, they
fall under the export retention policy (section 4.4).

Command output may contain lead names, message excerpts, and (in approval
dry-run mode) the full draft and related notes. Cron output is written to
`/var/openclaw/logs/`; treat those logs as personal-data-bearing and apply an
operator-defined retention period.

### 2.6 Exports

Operator-created exports (CSV, text) of lead data are written to
`/var/openclaw/exports/` on the Mac mini. These are outside git but may
contain identifiable information. Apply the retention limits in section 4.4.

### 2.7 Backups

The runbook's backup command archives `/var/openclaw/clients/` (including JSONL
files) to `/var/openclaw/backups/`; it does not include logs, exports, or
secrets. Check any separate system-level backup scope before assuming those
paths are covered. See section 4.5 for backup retention.

---

## 3. Where Data Lives

```
In the private Git repository:
  clients/<slug>/config.yaml        -- client settings; real values may be personal data
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

The example config is fictional. The current config loader reads client
configs from `clients/<slug>/config.yaml`, and the production runbook instructs
operators to commit them. Real configs can contain personal data, particularly
for sole traders (for example, a person's name, direct contact details, or
location). A private repository is not a secrets vault or a guarantee that
information is non-personal. Minimise real config data, restrict repository
access, and review its history/retention before onboarding a real client.
Never put lead records or credentials there. Moving real configs out of Git
requires a code change because the current loader only supports repository
configs.

The current workflow does not call an external model. If a future adapter sends
lead data to an external model provider, that transfer must be assessed and
documented before real data is processed.

See `docs/local-state.md` for the canonical runtime directory layout.

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

The fictional example config uses 365 and 730 days. These are example values,
not recommended legal or industry defaults. Select and document periods per
client based on the actual purpose, business need, and applicable requirements.

### 4.2 Meaning of the Retention Fields

**lead_retention_days:** The configured target age, measured from receipt, at
which the operator should review and delete or minimise the full lead record,
unless a documented reason supports keeping it longer. It is not a minimum
holding period.

**delete_pii_after_days:** The configured outer target age, measured from
receipt, by which PII must be removed from any lead or associated draft records
that are still retained. Data may be deleted earlier. The schema requires this
value to be at least `lead_retention_days`.

These values are validated when loading config, but the workflow does not
calculate due dates, notify the operator, redact data, or delete records. The
operator must track and perform the actions manually using section 5.1. No
automated deletion script exists in the current version.

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

Backups in `/var/openclaw/backups/` contain copies of client JSONL files,
including personal data. Suggested baseline, matching the production runbook:
keep at least the last four weekly backups (about 35 days) and delete older
archives. This does not provide 12-month monthly backups; if a client needs
longer retention, define and test a separate schedule before changing the
cleanup command.

See `runbooks/mac-mini-production.md` Section 7 for the backup procedure.

---

## 5. Operator Procedures

### 5.1 Deleting or Redacting a Lead

No automated deletion tool exists in the current MVP. To delete or redact
a lead manually:

1. Record the request and date received, then identify the lead ID by checking
   `leads.jsonl` for the contact details. `list_leads` shows lead ID, name, and
   status; it does not search by email.
2. Identify every related record in `drafts.jsonl` and `audit.jsonl` by lead ID.
   Drafts may repeat personal data from the original enquiry.
3. Take a protected backup before changing data. Treat it as live personal
   data and delete temporary copies when the operation is verified.
4. `leads.jsonl` contains the current snapshot, not a history of versions;
   status updates rewrite the file. Redact or remove the matching record by
   rewriting valid JSONL, not by appending a duplicate record.
5. `drafts.jsonl` and `audit.jsonl` are append-only. Remove or redact all
   matching draft records as required. Audit events reference the lead ID;
   decide and record whether the applicable policy permits keeping those
   pseudonymous events or requires removing them too. Removing audit events
   affects the audit trail.
6. Record the action in a restricted operator log with the date, lead ID,
   reason, and who performed it. Verify the resulting files parse and contain
   no data that should have been removed.

No supported deletion/redaction command exists. This manual procedure is
error-prone and should be treated as an exceptional, checked operation; do not
promise completion until state files, exports, backups, and any sent messages
have been reviewed.

### 5.2 Handling a Subject Access or Deletion Request

If a lead contacts you requesting access to or deletion of their data:

1. Record the date received and promptly escalate the request to the operator
   and relevant client. Confirm identity only where reasonably necessary.
2. Locate their records by checking lead contact fields in `leads.jsonl`;
   `list_leads` does not search by email. Then locate associated draft and audit
   records by lead ID.
3. For an access request: compile all relevant records in `leads.jsonl`,
   `drafts.jsonl`, and `audit.jsonl` that reference their lead ID. This is a
   first-pass inventory, not necessarily all data held.
4. For a deletion request: follow the procedure in section 5.1 to remove
   or redact all records referencing their lead ID.
5. Check `/var/openclaw/logs/` and `/var/openclaw/exports/` for records or
   output containing their data; delete or redact as applicable.
6. Check `/var/openclaw/backups/` -- backups may contain historical copies.
   Decide whether to delete or rotate the backup based on the request and
   legal advice.
7. If you sent a Telegram notification about this lead, it may persist in
   Telegram's servers. This system has no message-deletion function; use
   Telegram's own controls where available.
8. Check any other systems actually used for this client. No OpenClaw/model
   provider is called by the current implementation; reassess this step if an
   external model adapter or other integration is enabled.
9. Apply the response deadline and any exemptions that actually apply to the
   request. Seek qualified advice if uncertain; do not promise completion until
   the search and action have been verified.

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
4. **Notify:** Immediately alert the relevant client/controller. If acting as a
   processor, notify the controller without undue delay. The controller must
   assess whether the breach is notifiable; a notifiable UK GDPR breach must
   generally be reported to the ICO without undue delay and, where feasible,
   within 72 hours. Whether affected people must also be notified depends on
   the risk. Follow the applicable contract and get qualified advice if unsure.
   See the [ICO processor guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/controllers-and-processors/controllers-and-processors/what-does-it-mean-if-you-are-a-processor/)
   and [ICO breach guidance](https://ico.org.uk/for-organisations/report-a-breach/personal-data-breach/personal-data-breaches-a-guide/).
5. **Fix:** Correct the configuration or process that caused the error before
   resuming operations.
6. **Review:** After the incident, review whether any system change is needed
   to prevent recurrence.

---

## 6. Telegram PII Minimisation

The system applies two controls to limit personal data in Telegram messages:

**1. Field selection:** Notifications include the lead name and a 300-character
excerpt, but also classification details and the full draft reply, which can
repeat personal data. Email and phone fields are not included directly.

**2. Redaction regex:** The `redact_contact_details()` function strips detected
email addresses and phone numbers from the original message excerpt only. It
does not scan or redact the draft, classification, lead name, or other fields.

**Current limits of these controls:**
- Name is included and is not redacted.
- The excerpt may contain other PII (addresses, NI numbers, account details)
  not caught by the email/phone regex.
- Draft reply text may reference the lead's name or business context.
- Telegram messages are stored on Telegram's servers. This system has no
  message-deletion function; use Telegram's own controls where available.

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

This is enforced for customer-facing first replies and follow-ups at the schema
level: `auto_send.first_reply` and `auto_send.followups` must both be `false` in
the MVP. The schema validator rejects any config that sets either to `true`.
The current assistant workflow is deterministic and local; no live OpenClaw
model adapter is implemented.

The approval workflow is:

1. `process_new_leads` or `process_due_followups` generates a draft reply.
2. In live mode, `notify_approvals` sends the draft to the operator via
   Telegram for review; in dry-run mode it prints the message locally.
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
- [ ] The client has been informed which systems process enquiries and that
      customer-facing replies are reviewed and sent by a human operator.
- [ ] The website privacy notice accurately describes current processing.
      Update it before enabling external AI/model processing; get legal review.
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
- Third-party processing and sub-processor obligations (currently GitHub for
  repository/config data and Telegram for live notifications; OpenClaw or a
  model provider only if a future adapter is enabled)
- Subject access and erasure request obligations and timescales
- Breach notification obligations under Article 33 UK GDPR

---

*For directory layout see `docs/local-state.md`.*
*For backup and deletion procedures see `runbooks/mac-mini-production.md` Section 7.*
*For daily and weekly operator checklists see `runbooks/mac-mini-production.md` Section 12.*
