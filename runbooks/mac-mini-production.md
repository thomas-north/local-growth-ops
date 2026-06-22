# Mac Mini Production Runbook

Operator guide for running the local-growth-ops assistant on the dedicated Mac mini.

This runbook covers first-time setup, daily operation, backup, recovery, and
client management. It is intended for one operator who has access to the Mac mini
and the private GitHub repo.

All customer-facing messages remain human-approved. Nothing in this runbook
enables automatic sending.

---

## 1. Prerequisites

### Hardware and OS

- Dedicated Mac mini (Apple Silicon or Intel)
- macOS 13 Ventura or later
- Admin access to the machine

### Software

- Git (included with Xcode Command Line Tools)
- Homebrew (https://brew.sh)
- Python 3.11 (installed via Homebrew -- see Section 2.2)
- GitHub SSH key configured for the thomas-north org

Verify the basics before proceeding:

```bash
git --version
brew --version
python3.11 --version   # must be 3.11.x
```

---

## 2. First-time Setup

### 2.1 Repository Checkout

```bash
cd ~
git clone git@github.com:thomas-north/local-growth-ops.git
cd local-growth-ops
```

Verify the clone:

```bash
ls clients/ lead_hub/ runbooks/ planning/ docs/
```

### 2.2 Python 3.11 Install

The system Python on older macOS is 3.9. Install 3.11 via Homebrew:

```bash
brew install python@3.11
python3.11 --version   # expect: Python 3.11.x
```

The path will be `/opt/homebrew/bin/python3.11` on Apple Silicon or
`/usr/local/bin/python3.11` on Intel.

### 2.3 State Root Directory

All live state lives at `/var/openclaw/` outside the repo. Create it:

```bash
sudo mkdir -p /var/openclaw/clients /var/openclaw/logs \
  /var/openclaw/exports /var/openclaw/backups /var/openclaw/secrets
sudo chown -R "$(whoami)" /var/openclaw
chmod 700 /var/openclaw/secrets
```

Verify:

```bash
ls /var/openclaw/
# clients  logs  exports  backups  secrets
```

If `/var/` is not writable (some dev machines), use `~/openclaw-state/` as a
temporary alternative and set:

```bash
export LOCAL_GROWTH_STATE_ROOT="$HOME/openclaw-state"
```

All documentation and commands use `/var/openclaw/` as the canonical path.

### 2.4 Secrets Files

Secrets live in `/var/openclaw/secrets/` and are never committed to git.
Create them from the template below, replacing placeholder values:

```bash
# /var/openclaw/secrets/telegram.env
# Load this before running notify_approvals in live mode.

TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-operator-chat-id-here
```

```bash
# /var/openclaw/secrets/clients.env
# Per-client webhook signing secrets (one line per client).
# Format: WEBHOOK_SECRET_<CLIENT_SLUG>=<value>
# Example: WEBHOOK_SECRET_EXAMPLE_CLIENT=placeholder

WEBHOOK_SECRET_EXAMPLE_CLIENT=placeholder
```

Set permissions:

```bash
chmod 600 /var/openclaw/secrets/*.env
```

To source secrets before running live commands:

```bash
source /var/openclaw/secrets/telegram.env
```

Never paste real tokens into shell history. Use `source` rather than `export`
on the command line.

### 2.5 Dependency Install

From inside the repo:

```bash
cd ~/local-growth-ops
python3.11 -m pip install -e ".[dev]"
```

Verify:

```bash
python3.11 -c "import lead_hub; print('OK')"
```

### 2.6 Config Validation

Validate the example client config to confirm the install is working:

```bash
python3.11 -m lead_hub.validate_client example-client
# OK: 'example-client' config is valid (Bright Spark Electrical, 5 service(s))
```

For a real client:

```bash
python3.11 -m lead_hub.validate_client <client-slug>
```

### 2.7 Smoke Test (Dry-run)

Run a full dry-run pipeline against a temp state root to confirm all commands
work before touching live state:

```bash
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead example-client \
  --name "Smoke Test" --email "smoke@example.invalid" \
  --service "eicr" --message "Please quote for an EICR"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.notify_approvals \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.weekly_report example-client
echo "Smoke test passed."
```

All commands should exit 0.

---

## 3. Daily Workflow

Run these steps each time you want to process leads. In the initial MVP, this
is a manual operator action rather than a fully automated cron job.

Always use `/var/openclaw/` as the state root in production:

```bash
export LOCAL_GROWTH_STATE_ROOT="/var/openclaw"
```

### 3.1 Source Secrets

```bash
source /var/openclaw/secrets/telegram.env
```

### 3.2 Ingest Website Leads (if applicable)

If a website payload file has arrived:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.ingest_website_payload \
  <client-slug> /path/to/payload.json
```

For manual test leads during pilots:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.manual_lead \
  <client-slug> \
  --name "Lead Name" --email "lead@example.com" \
  --service "eicr" --message "Please quote for an EICR"
```

### 3.3 Process New Leads

Classify all leads with status `new` and produce draft replies:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.process_new_leads \
  <client-slug> --dry-run
```

Leads move from `new` to `awaiting_approval` (genuine) or `escalated`/`spam`.

### 3.4 Send Approval Notifications

Send Telegram notifications for all `awaiting_approval` leads that have a
draft reply ready:

Dry-run (print to terminal, no Telegram call):

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.notify_approvals \
  <client-slug> --dry-run
```

Live (sends to Telegram -- requires secrets sourced):

```bash
source /var/openclaw/secrets/telegram.env
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.notify_approvals \
  <client-slug>
```

### 3.5 Review and Approve Drafts

After receiving the Telegram notification, the operator reviews the draft in
the notification. If approved:

1. Copy the draft reply from the notification.
2. Send it manually via email/phone (no auto-send in MVP).
3. Mark the lead as replied and schedule its first follow-up:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 - <<'PY'
from datetime import datetime, timedelta, timezone
from lead_hub.config_loader import load_client_config
from lead_hub.schemas.lead import LeadStatus
from lead_hub.storage import read_leads, update_lead_status

client_slug = "<client-slug>"
lead_id = "<lead-id>"

config = load_client_config(client_slug)
lead = next(l for l in read_leads(client_slug) if l.lead_id == lead_id)
next_followup = datetime.now(tz=timezone.utc) + timedelta(
    days=config.followup.first_followup_days
)
update_lead_status(
    client_slug,
    lead.lead_id,
    LeadStatus.replied,
    next_followup_at=next_followup,
)
print(f"Marked {lead.lead_id[:8]} as replied; next follow-up at {next_followup.isoformat()}")
PY
```

A convenience `mark_replied` CLI may be added in a future plan. Until then, use
the snippet above after manually sending an approved reply.

### 3.6 Process Due Follow-ups

Identify and draft follow-ups for leads whose next_followup_at is past:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.list_due_followups \
  <client-slug>

LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.process_due_followups \
  <client-slug> --dry-run
```

Review follow-up drafts the same way as first replies.

### 3.7 Weekly Report

Generate the weekly summary:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.weekly_report \
  <client-slug>
```

Pipe to a file for records:

```bash
LOCAL_GROWTH_STATE_ROOT="/var/openclaw" python3.11 -m lead_hub.weekly_report \
  <client-slug> > /var/openclaw/exports/<client-slug>-report-$(date +%Y-%m-%d).txt
```

---

## 4. Telegram Setup and Verification

### Creating the Bot

1. Open Telegram and message @BotFather.
2. Send `/newbot` and follow the prompts.
3. Copy the token you receive -- it is the TELEGRAM_BOT_TOKEN value.
4. Add the bot to your operator group or start a private chat with it.
5. Write the token to `/var/openclaw/secrets/telegram.env`, source it, send a
   message in the chat, then fetch the chat ID:

```bash
. /var/openclaw/secrets/telegram.env
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | python3.11 -m json.tool
# Look for "chat": {"id": ...} in the result.
```

6. Add the chat ID to `/var/openclaw/secrets/telegram.env`:

```bash
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat-id>
```

Do not paste the real bot token directly into shell commands. Keep it in the
secrets file and reference it through the environment variable.

### Verifying Notifications Work

```bash
source /var/openclaw/secrets/telegram.env
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead example-client \
  --name "Telegram Test" --email "tg@example.invalid" \
  --service "eicr" --message "Telegram verification test"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads \
  example-client --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.notify_approvals \
  example-client
# Check Telegram for the approval message.
```

---

## 5. Openclaw Onboarding (Future Step)

Openclaw is the AI assistant layer that will replace the current deterministic
dry-run adapter. This section is a placeholder for when Openclaw credentials
are available.

At that point:

- Install the Openclaw CLI or gateway per the Openclaw documentation.
- Start the gateway process and confirm it is running.
- Add any required Openclaw credentials to `/var/openclaw/secrets/`.
- The `--dry-run` flag on `process_new_leads` and `process_due_followups` will
  be extended to select the live Openclaw adapter rather than the local
  keyword-heuristic adapter.

Until Openclaw is connected, the dry-run adapter produces all drafts and the
workflow is otherwise identical.

Do not add Openclaw credentials to git, client config files, or any file under
this repo.

---

## 6. Cron Scheduling

The MVP workflow is designed to be run manually by the operator. If you want to
schedule the classify and notify steps, a cron job is appropriate.

IMPORTANT: The cron job must NEVER send messages to leads automatically.
notify_approvals sends Telegram messages to the OPERATOR for review -- not to
customers. The operator then takes manual action.

Example crontab entries (run `crontab -e` to edit):

```
# Run at 08:00 every weekday (Mon-Fri).
# Adjust the client slug and paths as needed.

# Source secrets and process new leads
0 8 * * 1-5 . /var/openclaw/secrets/telegram.env && \
  LOCAL_GROWTH_STATE_ROOT="/var/openclaw" \
  /opt/homebrew/bin/python3.11 -m lead_hub.process_new_leads <client-slug> \
  --dry-run >> /var/openclaw/logs/followup-assistant.log 2>&1

# Send operator approval notifications
5 8 * * 1-5 . /var/openclaw/secrets/telegram.env && \
  LOCAL_GROWTH_STATE_ROOT="/var/openclaw" \
  /opt/homebrew/bin/python3.11 -m lead_hub.notify_approvals <client-slug> \
  >> /var/openclaw/logs/followup-assistant.log 2>&1
```

Use absolute paths in crontab because the PATH is minimal in cron.

On Intel Macs replace `/opt/homebrew/bin/python3.11` with
`/usr/local/bin/python3.11`.

For Apple Silicon you can confirm the path with:

```bash
which python3.11
```

---

## 7. Backup Procedure

The only irreplaceable data is `/var/openclaw/clients/`. The repo itself can
be recloned.

### Weekly Backup

```bash
BACKUP_DATE=$(date +%Y-%m-%d)
tar -czf /var/openclaw/backups/leads-${BACKUP_DATE}.tar.gz \
  -C /var/openclaw clients/
```

Verify the backup:

```bash
tar -tzf /var/openclaw/backups/leads-${BACKUP_DATE}.tar.gz | head -20
```

### Off-site Copy

Copy the backup archive to an off-site location (external drive, encrypted
cloud storage). Do not use a public cloud service without encryption.

Example using macOS Time Machine: ensure `/var/openclaw/` is included in the
Time Machine backup scope.

### Backup Retention

Keep at least four weekly backups. Remove older ones manually or via a cron job:

```bash
# Remove backups older than 35 days
find /var/openclaw/backups/ -name "leads-*.tar.gz" -mtime +35 -delete
```

---

## 8. Log Locations

| Log | Path | Notes |
|-----|------|-------|
| Main assistant log | `/var/openclaw/logs/followup-assistant.log` | Written by cron commands |
| Intake log | `/var/openclaw/logs/intake.log` | Written by ingest_website_payload |
| Audit trail | `/var/openclaw/clients/<slug>/audit.jsonl` | Append-only, per client |

### Tailing Logs

```bash
tail -f /var/openclaw/logs/followup-assistant.log
```

### Checking the Audit Trail

```bash
python3.11 -c "
import json, sys
for line in open('/var/openclaw/clients/<client-slug>/audit.jsonl'):
    row = json.loads(line)
    print(row['occurred_at'][:16], row['kind'], row['lead_id'][:8], row['detail'][:60])
"
```

---

## 9. Reboot Recovery

After a reboot, verify the following before resuming operation:

1. Python 3.11 is still accessible:

```bash
python3.11 --version
```

2. The repo is still present and on the correct branch:

```bash
cd ~/local-growth-ops && git status
```

3. Dependencies are installed:

```bash
python3.11 -c "import lead_hub; print('OK')"
```

4. State root is accessible:

```bash
ls /var/openclaw/clients/
```

5. Secrets files are present (do NOT print their contents):

```bash
ls /var/openclaw/secrets/
# expect: telegram.env  clients.env
```

6. Validate active client configs:

```bash
python3.11 -m lead_hub.validate_client <client-slug>
```

7. Run the smoke test from Section 2.7 if anything seems wrong.

If cron jobs were configured, verify they are still present:

```bash
crontab -l
```

---

## 10. Adding a New Client

### Step 1 -- Create the Config

Copy the example config as a template:

```bash
cp -r clients/example-client clients/<new-slug>
```

Edit `clients/<new-slug>/config.yaml`:

- Set `client_id` and `client_slug` to the new slug (must match).
- Fill in `business`, `services`, `hours`, `tone`, `escalation_triggers`.
- Set `approval.telegram_chat_id: ""` (real chat ID goes in secrets, not here).
- Leave `auto_send.first_reply: false` and `auto_send.followups: false`.

### Step 2 -- Validate the Config

```bash
python3.11 -m lead_hub.validate_client <new-slug>
```

### Step 3 -- Create the State Directory

The state directory is created automatically when the first lead is ingested.
You can also create it manually:

```bash
mkdir -p /var/openclaw/clients/<new-slug>
```

### Step 4 -- Test with a Manual Lead

```bash
TMP="$(mktemp -d)"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.manual_lead <new-slug> \
  --name "Test Lead" --email "test@example.invalid" \
  --service "<service-slug>" --message "Test enquiry"
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.process_new_leads \
  <new-slug> --dry-run
LOCAL_GROWTH_STATE_ROOT="$TMP" python3.11 -m lead_hub.weekly_report <new-slug>
```

### Step 5 -- Commit the Config

```bash
git add clients/<new-slug>/config.yaml
git commit -m "feat(clients): add config for <new-slug>"
git push
```

Never commit state files (leads.jsonl, drafts.jsonl, audit.jsonl). The
`.gitignore` covers these.

---

## 11. Pausing and Resuming a Client

There is no automated mechanism to pause a client in the current MVP. The
operator pauses by simply not running the workflow commands for that client.

To make the pause explicit:

1. Add a `status: paused` comment to the top of the client config file.
2. Do not run `process_new_leads`, `notify_approvals`, or
   `process_due_followups` for that client's slug.

To resume, remove the comment and rerun the workflow commands.

A future plan may add a `paused` field to the config schema and enforcement
in the CLI commands.

---

## 12. Daily and Weekly Checklists

### Daily Checklist

Run each morning (or on arrival at the machine):

- [ ] Source secrets: `source /var/openclaw/secrets/telegram.env`
- [ ] Run `process_new_leads <client-slug> --dry-run` for each active client.
- [ ] Run `notify_approvals <client-slug>` for each active client.
- [ ] Check Telegram for approval notifications.
- [ ] Review and act on any approval notifications (copy draft, send manually,
      mark lead as replied).
- [ ] Check for escalated leads via `list_leads <client-slug>` -- contact the
      business owner as needed.
- [ ] Run `process_due_followups <client-slug> --dry-run` for each active client.

### Weekly Checklist

Run once a week (e.g. Monday morning):

- [ ] Generate weekly report: `weekly_report <client-slug>` for each client.
- [ ] Back up lead state: `tar -czf /var/openclaw/backups/leads-$(date +%Y-%m-%d).tar.gz -C /var/openclaw clients/`
- [ ] Confirm no secrets in git: `git log --oneline -10` -- no tokens or IDs.
- [ ] Confirm secrets files are present and readable:
      `ls -la /var/openclaw/secrets/`
- [ ] Check log size: `wc -l /var/openclaw/logs/followup-assistant.log`
- [ ] Review any leads stuck in `awaiting_approval` for more than 48 hours.
- [ ] Review and update client configs if business info has changed.

---

## 13. Troubleshooting

### python3.11: command not found

Install via Homebrew:

```bash
brew install python@3.11
```

Then confirm:

```bash
/opt/homebrew/bin/python3.11 --version
```

Add Homebrew to your PATH if needed (add to `~/.zshrc`):

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### ModuleNotFoundError: No module named 'lead_hub'

Re-install the package:

```bash
cd ~/local-growth-ops
python3.11 -m pip install -e ".[dev]"
```

### ERROR: Config identity mismatch

The `client_id` field in `clients/<slug>/config.yaml` does not match the
directory slug. Edit the file and ensure `client_id` and `client_slug` both
equal the directory name.

### ERROR: TELEGRAM_BOT_TOKEN env var is not set

Run:

```bash
source /var/openclaw/secrets/telegram.env
```

Or use `--dry-run` to skip Telegram and print the message to the terminal.

### notify_approvals sends no notifications

Possible causes:

1. No leads in `awaiting_approval` status -- check with `list_leads`.
2. The lead's AssistantRun has no `draft_reply` (spam or escalated leads do
   not get drafts). Check `list_leads` for the lead's status.
3. The notification was already sent for this run -- the command skips leads
   whose most recent run already has a `notification_sent` audit event.

### process_due_followups finds no leads

`list_due_followups` returns leads where `next_followup_at <= now`. If no
leads appear:

- The lead may not have `next_followup_at` set. This is set automatically
  when `process_due_followups` runs for the first follow-up, but the lead
  must first be in `replied` or `followup_scheduled` status.
- Check the lead's status with `list_leads`.

### Lead stuck in awaiting_approval

The operator has not yet manually sent the draft and marked the lead replied.
In the current MVP there is no auto-send. Review the approval notification and
act on it manually.

### /var/openclaw/ is not writable

Set `LOCAL_GROWTH_STATE_ROOT` to a writable path:

```bash
export LOCAL_GROWTH_STATE_ROOT="$HOME/openclaw-state"
mkdir -p "$LOCAL_GROWTH_STATE_ROOT/clients"
```

Add this export to `~/.zshrc` if using it permanently.

### Cron job not running

Verify the crontab is present:

```bash
crontab -l
```

Check the log:

```bash
tail -50 /var/openclaw/logs/followup-assistant.log
```

Common cron issues on macOS:
- Grant "Full Disk Access" to `/usr/sbin/cron` in System Settings >
  Privacy and Security > Full Disk Access.
- Use absolute paths to all executables in the crontab.
- Source secrets inside the cron command with `.`; cron does not inherit shell env.

---

*This runbook covers the supervised MVP workflow only. No customer-facing messages
are sent automatically. All operator actions require human review and manual send.*
