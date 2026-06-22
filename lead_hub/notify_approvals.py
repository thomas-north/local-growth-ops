"""
lead_hub.notify_approvals
~~~~~~~~~~~~~~~~~~~~~~~~~
Send operator approval notifications to Telegram for pending draft replies.

Usage::

    python3.11 -m lead_hub.notify_approvals <client-slug> [--dry-run]

Dry-run mode (``--dry-run``) prints the formatted approval message to stdout
and does NOT contact Telegram. Use it to verify message content without
credentials.

Live mode requires:
  TELEGRAM_BOT_TOKEN  — Bot API token (from /var/openclaw/secrets/telegram.env)
  TELEGRAM_CHAT_ID    — Operator chat ID (env var or config.approval.telegram_chat_id)

Only leads with status ``awaiting_approval`` and a non-None ``draft_reply``
receive a notification. Escalated, spam, and out-of-scope leads are silently
skipped.

Exits 0 on success (including zero pending leads), 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone

from lead_hub.config_loader import load_client_config
from lead_hub.schemas.assistant_workflow import AssistantRun, AuditEvent, AuditEventKind
from lead_hub.schemas.lead import LeadStatus
from lead_hub.storage import (
    append_audit_event,
    read_audit_events,
    read_assistant_runs,
    read_leads,
)
from lead_hub.telegram_approval import (
    TelegramSendError,
    format_approval_message,
    resolve_bot_token,
    resolve_chat_id,
    send_telegram_message,
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}

    if len(positional) < 1:
        print(
            "Usage: python3.11 -m lead_hub.notify_approvals"
            " <client-slug> [--dry-run]",
            file=sys.stderr,
        )
        return 2

    client_slug = positional[0]
    dry_run = "--dry-run" in flags

    # 1. Validate client config.
    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # 2. Resolve credentials (only required in live mode).
    bot_token: str | None = None
    chat_id: str | None = None
    if not dry_run:
        bot_token = resolve_bot_token()
        if not bot_token:
            print(
                "ERROR: TELEGRAM_BOT_TOKEN env var is not set. "
                "Set it from /var/openclaw/secrets/telegram.env or use --dry-run.",
                file=sys.stderr,
            )
            return 1
        chat_id = resolve_chat_id(config)
        if not chat_id:
            print(
                "ERROR: No Telegram chat ID found. Set TELEGRAM_CHAT_ID env var "
                "or populate config.approval.telegram_chat_id.",
                file=sys.stderr,
            )
            return 1

    # 3. Load leads and AssistantRun records.
    leads = read_leads(client_slug)
    pending = [l for l in leads if l.status == LeadStatus.awaiting_approval]

    if not pending:
        print(f"OK: no leads awaiting approval for {client_slug!r}")
        return 0

    runs = read_assistant_runs(client_slug)
    runs_by_lead: dict[str, AssistantRun] = {r.lead_id: r for r in runs}
    notified_run_ids = {
        event.detail.rsplit("Run ID: ", 1)[1].rstrip(".")
        for event in read_audit_events(client_slug)
        if event.kind == AuditEventKind.notification_sent
        and "Run ID: " in event.detail
    }

    sent = 0
    skipped = 0
    errors = 0

    for lead in pending:
        run = runs_by_lead.get(lead.lead_id)
        if run is None:
            print(
                f"SKIP: {lead.lead_id[:8]}  {lead.name} — no AssistantRun found",
                file=sys.stderr,
            )
            continue
        if run.draft_reply is None:
            print(
                f"SKIP: {lead.lead_id[:8]}  {lead.name} — no draft reply in run",
                file=sys.stderr,
            )
            continue
        if run.run_id[:8] in notified_run_ids:
            print(
                f"SKIP: {lead.lead_id[:8]}  {lead.name} — approval notification already sent for run {run.run_id[:8]}",
                file=sys.stderr,
            )
            skipped += 1
            continue

        # 4a. Format message.
        try:
            message_text = format_approval_message(lead, run, config)
        except Exception as exc:
            print(f"ERROR: could not format message for {lead.lead_id[:8]}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # 4b. Send or print.
        if dry_run:
            print(f"\n{'─' * 60}")
            print(f"DRY-RUN: approval message for {lead.lead_id[:8]} ({lead.name})")
            print(f"{'─' * 60}")
            print(message_text)
        else:
            try:
                send_telegram_message(message_text, chat_id, bot_token)  # type: ignore[arg-type]
            except TelegramSendError as exc:
                print(
                    f"ERROR: Telegram send failed for {lead.lead_id[:8]}: {exc}",
                    file=sys.stderr,
                )
                errors += 1
                continue

        # 4c. Audit log.
        try:
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                lead_id=lead.lead_id,
                client_id=config.client_id,
                kind=AuditEventKind.notification_sent,
                occurred_at=datetime.now(tz=timezone.utc),
                detail=(
                    f"Approval notification {'printed (dry-run)' if dry_run else 'sent via Telegram'}. "
                    f"Run ID: {run.run_id[:8]}."
                ),
                previous_status=lead.status,
                new_status=lead.status,  # status unchanged by notification
            )
            append_audit_event(client_slug, event)
        except Exception as exc:
            print(f"WARN: could not write audit event for {lead.lead_id[:8]}: {exc}", file=sys.stderr)

        mode = "dry-run" if dry_run else "sent"
        print(f"OK: {lead.lead_id[:8]}  {lead.name:<25}  notification {mode}")
        sent += 1

    summary_suffix = " (dry-run)" if dry_run else ""
    print(
        f"\nDone: {sent} notification(s){summary_suffix}, "
        f"{skipped} already notified, {errors} error(s)."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
