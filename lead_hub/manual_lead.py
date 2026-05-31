"""
lead_hub.manual_lead
~~~~~~~~~~~~~~~~~~~~
Create a manual/test lead for a client and store it in the lead hub.

Usage::

    python3.11 -m lead_hub.manual_lead <client-slug> [options]

Options::

    --name TEXT       Lead name (default: "Test Lead")
    --email TEXT      Contact email
    --phone TEXT      Contact phone
    --service TEXT    Service requested
    --message TEXT    Lead message (default: generic enquiry text)
    --urgency TEXT    low | normal | high | urgent (default: normal)

At least one of --email or --phone is required.

Exits 0 on success, 1 on error, 2 on usage error.
"""

from __future__ import annotations

import argparse
import sys

from lead_hub.config_loader import load_client_config
from lead_hub.schemas.intake import ManualLeadPayload, manual_payload_to_lead
from lead_hub.schemas.lead import Urgency
from lead_hub.storage import append_lead


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3.11 -m lead_hub.manual_lead",
        description="Create a manual test lead for a client.",
    )
    p.add_argument("client_slug", help="Client slug, e.g. example-client")
    p.add_argument("--name", default="Test Lead", help="Lead name")
    p.add_argument("--email", default=None, help="Contact email")
    p.add_argument("--phone", default=None, help="Contact phone")
    p.add_argument("--service", default="", help="Service requested")
    p.add_argument(
        "--message",
        default="Manual test lead — please quote for a job.",
        help="Lead message",
    )
    p.add_argument(
        "--urgency",
        choices=[u.value for u in Urgency],
        default=Urgency.normal.value,
        help="Urgency level (default: normal)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.email and not args.phone:
        print(
            "ERROR: at least one of --email or --phone is required",
            file=sys.stderr,
        )
        return 2

    # Validate client config before writing anything.
    try:
        config = load_client_config(args.client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = ManualLeadPayload(
        client_id=config.client_id,
        name=args.name,
        email=args.email or None,
        phone=args.phone or None,
        service_requested=args.service,
        message=args.message,
        urgency=Urgency(args.urgency),
    )

    lead = manual_payload_to_lead(payload)

    try:
        append_lead(args.client_slug, lead)
    except Exception as exc:
        print(f"ERROR: Failed to write lead: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: lead {lead.lead_id} created for {args.client_slug!r} "
        f"({lead.name}, status={lead.status.value})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
