"""
lead_hub.process_due_followups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Process leads whose follow-up date is due and generate operator-review drafts.

Usage::

    python3.11 -m lead_hub.process_due_followups <client-slug> [--dry-run]

The ``--dry-run`` flag selects the deterministic local scheduler adapter
(``followup-dry-run-v1``). Writes ARE performed: AssistantRun to drafts.jsonl,
AuditEvent to audit.jsonl, and lead status updated in leads.jsonl.

Leads in spam, escalated, closed, won, or lost status are silently skipped.
Leads that have reached max_followups are also skipped.

Exits 0 on success (including zero due leads), 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys

from lead_hub.config_loader import load_client_config
from lead_hub.followup_scheduler import (
    EXCLUDED_STATUSES,
    compute_next_followup_at,
    count_followup_drafts,
    make_followup_audit_event,
    run_followup_workflow,
)
from lead_hub.storage import (
    append_assistant_run,
    append_audit_event,
    list_due_followups,
    update_lead_status,
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}

    if len(positional) < 1:
        print(
            "Usage: python3.11 -m lead_hub.process_due_followups"
            " <client-slug> [--dry-run]",
            file=sys.stderr,
        )
        return 2

    client_slug = positional[0]
    _dry_run = "--dry-run" in flags  # reserved; adapter selection in future

    # 1. Validate client config.
    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # 2. Get due leads.
    try:
        due = list_due_followups(client_slug)
    except Exception as exc:
        print(f"ERROR: could not read leads: {exc}", file=sys.stderr)
        return 1

    if not due:
        print(f"OK: no follow-ups due for {client_slug!r}")
        return 0

    print(f"Processing {len(due)} due follow-up(s) for {client_slug!r}...\n")

    processed = 0
    skipped = 0
    errors = 0

    for lead in due:
        # 3. Skip excluded statuses.
        if lead.status in EXCLUDED_STATUSES:
            print(
                f"  SKIP: {lead.lead_id[:8]}  {lead.name} -- status={lead.status.value}",
                file=sys.stderr,
            )
            skipped += 1
            continue

        # 4. Count existing follow-up drafts.
        try:
            followup_count = count_followup_drafts(client_slug, lead.lead_id)
        except Exception as exc:
            print(f"  ERROR: could not count drafts for {lead.lead_id[:8]}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # 5. Skip if max reached.
        if followup_count >= config.followup.max_followups:
            print(
                f"  SKIP: {lead.lead_id[:8]}  {lead.name} -- max_followups ({config.followup.max_followups}) reached",
                file=sys.stderr,
            )
            skipped += 1
            continue

        previous_status = lead.status

        # 6. Run follow-up workflow.
        try:
            run = run_followup_workflow(lead, config, followup_count)
        except Exception as exc:
            print(f"  ERROR: workflow failed for {lead.lead_id[:8]}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # 7. Compute next follow-up date.
        next_followup = compute_next_followup_at(
            config, lead.received_at, followup_count + 1
        )

        # 8. Persist.
        try:
            append_assistant_run(client_slug, run)
            event = make_followup_audit_event(lead, run, previous_status, followup_count)
            append_audit_event(client_slug, event)
            update_lead_status(
                client_slug,
                lead.lead_id,
                run.new_status,
                next_followup_at=next_followup,
                clear_next_followup_at=(next_followup is None),
            )
        except Exception as exc:
            print(f"  ERROR: failed to write outputs for {lead.lead_id[:8]}: {exc}", file=sys.stderr)
            errors += 1
            continue

        has_draft = run.draft_reply is not None
        next_str = next_followup.strftime("%Y-%m-%d") if next_followup else "none (exhausted)"
        print(
            f"  OK: {lead.lead_id[:8]}  {lead.name:<25}"
            f"  followup {followup_count + 1}/{config.followup.max_followups}"
            f"{'  [draft ready]' if has_draft else '  [no draft -- escalated]'}"
            f"  next={next_str}"
        )
        processed += 1

    print(
        f"\nDone: {processed} processed, {skipped} skipped, {errors} error(s)."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
