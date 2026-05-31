# Local State — Where Operational Data Lives

All live operational data lives **outside this git repository** on the Mac mini.
Nothing described here should ever be committed.

## Mac Mini State Directory

Canonical root: **`/var/openclaw/`**

Use `~/openclaw-state/` only as a temporary alternative on a dev machine that
does not allow writing to `/var/`. All documentation, runbooks, and scripts
should reference `/var/openclaw/` as the authoritative path.

The structure is:

```
/var/openclaw/
  clients/
    example-client/
      leads.jsonl          # live lead records — never commit
      state.json           # runtime state (last run, counts) — never commit
    <real-client-slug>/
      leads.jsonl
      state.json
  logs/
    followup-assistant.log
    intake.log
  exports/
    <client-slug>-report-2026-05.csv
  backups/
    leads-2026-05-31.tar.gz
  secrets/
    telegram.env           # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS
    clients.env            # per-client form webhook signing secrets, etc.
```

## What Goes Where

| Data type | Location | Committed? |
|-----------|----------|------------|
| Client assistant config | `clients/<slug>/config.yaml` in repo | Yes (no secrets) |
| Live leads | `/var/openclaw/clients/<slug>/leads.jsonl` | **Never** |
| Runtime state | `/var/openclaw/clients/<slug>/state.json` | **Never** |
| Logs | `/var/openclaw/logs/` | **Never** |
| Exports / reports | `/var/openclaw/exports/` | **Never** |
| Backups | `/var/openclaw/backups/` | **Never** |
| Secrets / tokens | `/var/openclaw/secrets/*.env` | **Never** |

## Backup

Back up `/var/openclaw/` on a regular schedule (weekly minimum). The repo
itself does not contain anything that cannot be recloned; the state directory
is the only irreplaceable operational data.

See `runbooks/backup-procedure.md` (to be written in plan 0009).

## Secrets

Load secrets from environment files at runtime. Never hard-code tokens or
credentials in scripts, config files, or prompt templates.

Example (add to cron environment or `.env` file loaded at startup):

```bash
source /var/openclaw/secrets/telegram.env
python3.11 -m lead_hub.list_due_followups example-client
```
