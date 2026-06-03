"""
lead_hub.process_lead
~~~~~~~~~~~~~~~~~~~~~
Process a single lead through the classification and draft workflow.

Usage::

    python3.11 -m lead_hub.process_lead <client-slug> <lead-id> [--dry-run]

The ``--dry-run`` flag selects the deterministic local assistant (adapter
``dry-run-v1``). Writes ARE performed: AssistantRun → drafts.jsonl,
AuditEvent → audit.jsonl, and lead status updated in leads.jsonl.

In a later plan, omitting ``--dry-run`` will select the live Openclaw
adapter. For now, both paths use the dry-run implementation.

Exits 0 on success, 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys

from lead_hub.assistant import make_audit_event, run_workflow
from lead_hub.config_loader import load_client_config
from lead_hub.storage import (
    append_assistant_run,
    append_audit_event,
    read_leads,
    update_lead_status,
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    # Parse: <client-slug> <lead-id> [--dry-run]
    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}

    if len(positional) < 2:
        print(
            "Usage: python3.11 -m lead_hub.process_lead"
            " <client-slug> <lead-id> [--dry-run]",
            file=sys.stderr,
        )
        return 2

    client_slug, lead_id = positional[0], positional[1]
    _dry_run = "--dry-run" in flags  # reserved for future adapter selection

    # 1. Validate client config.
    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # 2. Find the lead.
    leads = read_leads(client_slug)
    lead = next((l for l in leads if l.lead_id == lead_id), None)
    if lead is None:
        print(
            f"ERROR: lead {lead_id!r} not found for client {client_slug!r}",
            file=sys.stderr,
        )
        return 1

    previous_status = lead.status

    # 3. Run workflow.
    try:
        run = run_workflow(lead, config)
    except Exception as exc:
        print(f"ERROR: workflow failed: {exc}", file=sys.stderr)
        return 1

    # 4. Persist outputs.
    try:
        append_assistant_run(client_slug, run)
        event = make_audit_event(lead, run, previous_status)
        append_audit_event(client_slug, event)
        update_lead_status(client_slug, lead_id, run.new_status)
    except Exception as exc:
        print(f"ERROR: failed to write outputs: {exc}", file=sys.stderr)
        return 1

    # 5. Print operator summary.
    cls = run.classification
    has_draft = run.draft_reply is not None
    print(
        f"OK: {lead_id[:8]}  {lead.name:<25}"
        f"  {cls.classification.value:<22}"
        f"  → {run.new_status.value}"
        f"{'  [draft ready]' if has_draft else '  [no draft]'}"
    )
    if run.escalation_check.escalation_required:
        print(f"    ESCALATION: {run.escalation_check.reasons[0] if run.escalation_check.reasons else '(see audit log)'}")
    if has_draft:
        print(f"    operator note: {run.draft_reply.operator_notes}")  # type: ignore[union-attr]

    return 0


if __name__ == "__main__":
    sys.exit(main())
