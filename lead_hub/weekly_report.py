"""
lead_hub.weekly_report
~~~~~~~~~~~~~~~~~~~~~~
Generate a plain-text weekly summary for an operator.

Usage::

    python3.11 -m lead_hub.weekly_report <client-slug>

Report sections:
- Report date and client name
- Lead counts by status
- Pending approvals (awaiting_approval) -- lead IDs and names only, no raw PII
- Follow-ups due now or overdue
- Open escalations
- Recommended operator actions

Output is plain text to stdout. No email delivery, no Telegram send in this plan.

Exits 0 on success, 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone

from lead_hub.config_loader import load_client_config
from lead_hub.schemas.lead import LeadStatus
from lead_hub.storage import list_due_followups, read_leads


def _build_report(client_slug: str, config, as_of: datetime) -> str:
    leads = read_leads(client_slug)
    due_followups = list_due_followups(client_slug, as_of=as_of)

    status_counts: Counter[str] = Counter(l.status.value for l in leads)
    pending = [l for l in leads if l.status == LeadStatus.awaiting_approval]
    escalated = [l for l in leads if l.status == LeadStatus.escalated]

    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("WEEKLY OPS REPORT")
    lines.append(f"Client:  {config.business.name}")
    lines.append(f"Date:    {as_of.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)
    lines.append("")

    # --- Lead summary ---
    lines.append("LEAD SUMMARY")
    lines.append("-" * 40)
    total = len(leads)
    lines.append(f"Total leads on record: {total}")
    if total == 0:
        lines.append("  (no leads yet)")
    else:
        for status in LeadStatus:
            count = status_counts.get(status.value, 0)
            if count:
                lines.append(f"  {status.value:<25} {count}")
    lines.append("")

    # --- Pending approvals ---
    lines.append("PENDING APPROVALS (awaiting_approval)")
    lines.append("-" * 40)
    if not pending:
        lines.append("  None.")
    else:
        for l in pending:
            lines.append(f"  {l.lead_id[:8]}  {l.name}")
    lines.append("")

    # --- Due follow-ups ---
    lines.append("FOLLOW-UPS DUE OR OVERDUE")
    lines.append("-" * 40)
    if not due_followups:
        lines.append("  None.")
    else:
        for l in due_followups:
            due_str = (
                l.next_followup_at.strftime("%Y-%m-%d")
                if l.next_followup_at
                else "unknown"
            )
            lines.append(f"  {l.lead_id[:8]}  {l.name:<25}  due {due_str}")
    lines.append("")

    # --- Open escalations ---
    lines.append("OPEN ESCALATIONS")
    lines.append("-" * 40)
    if not escalated:
        lines.append("  None.")
    else:
        for l in escalated:
            lines.append(f"  {l.lead_id[:8]}  {l.name}")
    lines.append("")

    # --- Recommended actions ---
    lines.append("RECOMMENDED OPERATOR ACTIONS")
    lines.append("-" * 40)
    actions: list[str] = []
    if pending:
        actions.append(
            f"Review {len(pending)} draft reply(s) awaiting approval "
            f"and run notify_approvals to send Telegram notification."
        )
    if due_followups:
        actions.append(
            f"Run process_due_followups to generate {len(due_followups)} "
            f"overdue follow-up draft(s)."
        )
    if escalated:
        actions.append(
            f"Manually review {len(escalated)} escalated lead(s) "
            f"and contact the business owner as appropriate."
        )
    won = status_counts.get("won", 0)
    lost = status_counts.get("lost", 0)
    if won or lost:
        actions.append(
            f"Archive or close leads: {won} won, {lost} lost."
        )
    if not actions:
        actions.append("No immediate actions required.")
    for action in actions:
        lines.append(f"  - {action}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("End of report.")
    lines.append("=" * 60)

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    positional = [a for a in args if not a.startswith("--")]

    if not positional:
        print(
            "Usage: python3.11 -m lead_hub.weekly_report <client-slug>",
            file=sys.stderr,
        )
        return 2

    client_slug = positional[0]

    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        report = _build_report(client_slug, config, as_of=datetime.now(tz=timezone.utc))
    except Exception as exc:
        print(f"ERROR: could not build report: {exc}", file=sys.stderr)
        return 1

    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
