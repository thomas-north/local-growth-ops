"""
lead_hub.list_leads
~~~~~~~~~~~~~~~~~~~
List all stored leads for a client.

Usage::

    python3.11 -m lead_hub.list_leads <client-slug>

Exits 0 on success (including empty list), 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys

from lead_hub.config_loader import load_client_config
from lead_hub.storage import read_leads


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: python3.11 -m lead_hub.list_leads <client-slug>",
            file=sys.stderr,
        )
        return 2

    client_slug = args[0]

    try:
        load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        leads = read_leads(client_slug)
    except Exception as exc:
        print(f"ERROR: Failed to read leads: {exc}", file=sys.stderr)
        return 1

    if not leads:
        print(f"No leads found for {client_slug!r}.")
        return 0

    print(f"Leads for {client_slug!r} ({len(leads)} total):\n")
    for lead in leads:
        followup = (
            lead.next_followup_at.strftime("%Y-%m-%d %H:%M UTC")
            if lead.next_followup_at
            else "—"
        )
        print(
            f"  {lead.lead_id[:8]}  "
            f"{lead.received_at.strftime('%Y-%m-%d %H:%M UTC')}  "
            f"{lead.status.value:<22}  "
            f"{lead.name:<25}  "
            f"followup: {followup}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
