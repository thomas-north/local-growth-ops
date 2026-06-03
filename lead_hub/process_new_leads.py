"""
lead_hub.process_new_leads
~~~~~~~~~~~~~~~~~~~~~~~~~~
Process all leads with status ``new`` for a client.

Usage::

    python3.11 -m lead_hub.process_new_leads <client-slug> [--dry-run]

Processes only leads in ``new`` status. Writes AssistantRun → drafts.jsonl,
AuditEvent → audit.jsonl, and updates each lead's status.

The ``--dry-run`` flag selects the deterministic local assistant adapter
(``dry-run-v1``). Writes are still performed. In a later plan, omitting
``--dry-run`` will select the live Openclaw adapter.

Exits 0 on success (including zero new leads), 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys

from lead_hub.assistant import make_audit_event, run_workflow
from lead_hub.config_loader import load_client_config
from lead_hub.schemas.lead import LeadStatus
from lead_hub.storage import (
    append_assistant_run,
    append_audit_event,
    read_leads,
    update_lead_status,
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    positional = [a for a in args if not a.startswith("--")]
    _flags = {a for a in args if a.startswith("--")}

    if not positional:
        print(
            "Usage: python3.11 -m lead_hub.process_new_leads"
            " <client-slug> [--dry-run]",
            file=sys.stderr,
        )
        return 2

    client_slug = positional[0]
    _dry_run = "--dry-run" in _flags

    # 1. Validate client config.
    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # 2. Load only new leads.
    all_leads = read_leads(client_slug)
    new_leads = [l for l in all_leads if l.status == LeadStatus.new]

    if not new_leads:
        print(f"No new leads to process for {client_slug!r}.")
        return 0

    print(f"Processing {len(new_leads)} new lead(s) for {client_slug!r}...\n")

    processed = 0
    errors = 0

    for lead in new_leads:
        previous_status = lead.status
        try:
            run = run_workflow(lead, config)
            append_assistant_run(client_slug, run)
            event = make_audit_event(lead, run, previous_status)
            append_audit_event(client_slug, event)
            update_lead_status(client_slug, lead.lead_id, run.new_status)
        except Exception as exc:
            print(f"  ERROR processing {lead.lead_id[:8]}: {exc}", file=sys.stderr)
            errors += 1
            continue

        cls = run.classification
        has_draft = run.draft_reply is not None
        print(
            f"  {lead.lead_id[:8]}  {lead.name:<25}"
            f"  {cls.classification.value:<22}"
            f"  → {run.new_status.value}"
            f"{'  [draft ready]' if has_draft else '  [no draft]'}"
        )
        processed += 1

    print(
        f"\nDone. {processed} processed, {errors} error(s)."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
