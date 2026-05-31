# Runbooks

Operator setup and production procedures for running the follow-up assistant
on the dedicated Mac mini.

## Planned Runbooks

These will be written in plan 0009:

```
mac-mini-setup.md          — initial Mac mini environment setup
gateway-startup.md         — starting and verifying the Openclaw gateway
telegram-check.md          — verifying Telegram operator notifications work
secrets-audit.md           — confirming no secrets are in git or wrong place
cron-setup.md              — configuring scheduled lead checks
backup-procedure.md        — backing up lead state and client configs
reboot-recovery.md         — restoring service after a restart
client-pause-resume.md     — pausing and resuming a client's assistant
```

## Daily Operator Checklist (draft)

- Openclaw gateway process is running.
- Telegram notifications are arriving.
- No leads have been stuck in "Needs reply draft" for more than 24 hours.

## Weekly Operator Checklist (draft)

- Weekly reports have been sent for all active clients.
- Lead JSONL files are backed up.
- No secrets have been introduced into git (run `git log --oneline -10`).
- Client configs are up to date.
