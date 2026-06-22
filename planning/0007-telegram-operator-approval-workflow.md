# Plan 0007: Implement Telegram Operator Approval Workflow

GitHub issue: #7, "Implement Telegram operator approval workflow"

## Goal

Allow the operator to review assistant-drafted replies from Telegram before
anything is sent to a customer. Nothing is ever sent automatically. The workflow
is notification-only in this plan — the operator approves by taking manual
action (mark replied, edit and send, escalate) using existing commands.

## Scope

Implement:

- Format operator approval messages from AssistantRun + NormalizedLead data
- Send formatted messages to Telegram via Bot API (token from env var)
- Dry-run mode that prints the message locally without contacting Telegram
- CLI command: `lead_hub.notify_approvals <client-slug> [--dry-run]`
- Only send for leads in `awaiting_approval` status with a non-None draft reply
- Minimise PII in Telegram messages (name and message excerpt only — no
  email/phone in chat)
- Audit log entry for each notification sent
- Tests with no real network calls (mock the HTTP sender)
- Update docs and README

Defer:

- Interactive Telegram buttons (approve/reject via callback)
- Auto-updating lead status from Telegram replies
- Weekly report delivery via Telegram
- Any email notification channel
- Sending the actual reply to the customer

## Safety Requirements

- No auto-send to leads. The approval message tells the operator a draft exists;
  the operator takes manual action to send it.
- No real Telegram API call in tests. Patch the HTTP sender function.
- No bot token or chat ID committed to git. Token from `TELEGRAM_BOT_TOKEN`
  env var; chat ID from `TELEGRAM_CHAT_ID` env var (overrides config value when
  set, so secrets stay outside git and config).
- Every approval message must include the phrase "approval required" so there is
  no ambiguity.
- Escalated, spam, and non-awaiting-approval leads must not produce a message.
- Draft must be non-None before sending notification.
- Audit log must be updated when a notification is sent (or attempted).

## Message Format

Telegram approval messages use Telegram Markdown (MarkdownV2 or plain text).
Use plain text to avoid escaping complexity in templates.

Required fields in every message:

1. Header: client name and notification purpose
2. Lead identity: name only (not email or phone — minimise PII in chat)
3. Lead message excerpt (first 300 characters)
4. Classification and confidence
5. Draft subject
6. Draft body
7. Assumptions (bullet list)
8. Questions for lead (bullet list)
9. Operator notes
10. Footer: clear statement that approval is required before any message is sent

## Architecture

```
lead_hub/
  telegram_approval.py   — message formatting and HTTP send function
  notify_approvals.py    — CLI entry point
```

### `telegram_approval.py`

Key public functions:

- `format_approval_message(lead, run, config) -> str`
  Build the full text of the approval notification. Minimises PII.

- `send_telegram_message(text, chat_id, bot_token) -> None`
  POST to `https://api.telegram.org/bot<token>/sendMessage` using
  `urllib.request`. Raises `TelegramSendError` on HTTP/network failure.
  Never called in tests — tests patch this function.

- `class TelegramSendError(RuntimeError)` — raised on send failure.

### `notify_approvals.py`

CLI: `python3.11 -m lead_hub.notify_approvals <client-slug> [--dry-run]`

Behaviour:

1. Validate client config (slug identity check).
2. Load leads → filter to `awaiting_approval`.
3. Load AssistantRun records from `drafts.jsonl` → match by `lead_id`.
4. For each matched pair with `draft_reply is not None`:
   a. Format approval message.
   b. Dry-run: print to stdout.
   c. Live: POST to Telegram using token + chat ID (env var overrides config).
   d. Append AuditEvent (kind=`notification_sent`).
5. Print summary line per lead.
6. Exit 0 on success, 1 on error, 2 on usage error.

Token resolution order:
1. `TELEGRAM_BOT_TOKEN` env var
2. (none — if absent and not dry-run, exit 1 with clear error)

Chat ID resolution order:
1. `TELEGRAM_CHAT_ID` env var
2. `config.approval.telegram_chat_id` (may be empty string in example config)
3. If neither has a value and not dry-run, exit 1 with clear error.

## Audit Event Extension

Add `notification_sent` to `AuditEventKind` in
`lead_hub/schemas/assistant_workflow.py`.

## Config

`ApprovalConfig.telegram_chat_id` already exists in the schema as an empty
string for the example client. This plan adds no new config fields — the chat
ID can be set via env var (`TELEGRAM_CHAT_ID`) or by the operator populating
the config's `telegram_chat_id` field at runtime.

## Local State

No new files. Existing audit log at:

```
/var/openclaw/clients/<client-slug>/audit.jsonl
```

receives a new `notification_sent` entry per lead notified.

## Tests

File: `tests/test_telegram.py`

Required cases:

- `format_approval_message` includes lead name and classification
- `format_approval_message` does NOT include lead email or phone number
- `format_approval_message` includes draft subject and draft body
- `format_approval_message` includes the phrase "approval required" (case-insensitive)
- `format_approval_message` includes operator notes
- Leads with status other than `awaiting_approval` are not included in notifications
- Leads without a draft reply are not included in notifications
- Escalated leads with status `escalated` are skipped
- Spam leads with status `spam` are skipped
- Dry-run mode prints message and does NOT call `send_telegram_message`
- Notification CLI writes an audit event per lead
- Missing `TELEGRAM_BOT_TOKEN` in live mode exits 1
- Missing chat ID (no env var and empty config) in live mode exits 1
- No-args CLI exits 2
- Missing client exits 1
- Zero pending leads exits 0 cleanly

Patches: monkeypatch `lead_hub.telegram_approval.send_telegram_message` to a
no-op or capture function. Never make real HTTP calls in tests.

## Verification Commands

```bash
python3.11 --version
python3.11 -m pip install -e ".[dev]"
python3.11 -m pytest tests/
python3.11 -m compileall lead_hub openclaw tests -q
# Dry-run end-to-end:
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead example-client \
  --name "Notify Test" --email "notify@example.invalid" --service "eicr" \
  --message "Please quote for an EICR for my rental property"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.notify_approvals example-client --dry-run
# Stale-reference check:
rg -n --pcre2 "python3(?!\.11)|python -m|state/<|config.example.yaml" \
  README.md docs lead_hub tests planning openclaw pyproject.toml
# Safety check (no real tokens or chat IDs in code):
rg -n "TELEGRAM_BOT_TOKEN\s*=|chat_id\s*=\s*\"-?[0-9]" lead_hub tests
```

## Documentation Updates

- `README.md`: add `notify_approvals` command, update development status (plan 0007 complete)
- `lead_hub/README.md`: add `notify_approvals` command, update What Does Not Belong Here
- `docs/local-state.md`: no new files needed; confirm audit.jsonl note covers notifications
- Plan checkboxes and execution notes

## Tasks

- [x] Create `planning/0007-telegram-operator-approval-workflow.md`
- [x] Add `notification_sent` to `AuditEventKind` in `assistant_workflow.py`
- [x] Create `lead_hub/telegram_approval.py` (format + send functions)
- [x] Create `lead_hub/notify_approvals.py` (CLI entry point)
- [x] Write tests in `tests/test_telegram.py`
- [x] Update `README.md` (command list, development status)
- [x] Update `lead_hub/README.md` (command docs, What Does Not Belong Here)
- [x] Run all verification commands
- [x] Update plan checkboxes and execution notes
- [x] Create branch `codex/ops-telegram-approval`
- [x] Commit and open draft PR linked to issue #7

## Branch And PR

- [x] Branch: `codex/ops-telegram-approval`
- [x] Draft PR linked to issue #7
- [x] PR description: approval message format, PII minimisation approach,
  token resolution, dry-run semantics, deferred interactive buttons, and
  verification commands run

## Execution Notes

**`send_telegram_message` uses `urllib.request`:** No new runtime dependency added.
The Telegram Bot API endpoint `POST /bot<token>/sendMessage` is called with a
plain JSON body. `httpx`/`requests` would also work but would require adding a
dependency; `urllib.request` is sufficient for this single endpoint.

**PII minimisation:** Lead email and phone number are intentionally excluded from
the Telegram message. The lead's name and a 300-character excerpt of their message
are the only contact-derived fields in the notification. The operator can retrieve
full contact details from `leads.jsonl` using `list_leads` if needed.

**Token resolution:** `TELEGRAM_BOT_TOKEN` (required for live sends) and
`TELEGRAM_CHAT_ID` (preferred over `config.approval.telegram_chat_id`) are always
sourced from environment variables so secrets are never in git or config files.
The example client config has empty strings for both approval fields by design.

**`notification_sent` AuditEventKind:** Added to the `AuditEventKind` enum in
`assistant_workflow.py`. The new status uses `previous_status == new_status`
(lead status is unchanged by a notification) to make it clear this is an
observation event, not a state transition.

**`--dry-run` semantics:** Consistent with plan 0006 semantics — dry-run uses the
deterministic local path and still performs writes (audit log). It does NOT make
any Telegram API calls. The flag makes `notify_approvals` safe to run in dev/CI
without credentials.

**Verification results:**
- `python3.11 --version`: 3.11.15 ✓
- `python3.11 -m pytest tests/`: 287 passed (63 config + 42 storage + 39 intake + 75 prompts + 38 workflow + 30 telegram) ✓
- `python3.11 -m compileall lead_hub openclaw tests -q`: clean ✓
- End-to-end dry-run: `manual_lead` → `process_new_leads --dry-run` → `notify_approvals --dry-run` prints full operator message ✓
- Stale-reference grep: all matches are historical execution notes or grep commands, not stale paths ✓
- Safety grep: no hardcoded tokens or chat IDs in `lead_hub/` or `tests/` ✓
