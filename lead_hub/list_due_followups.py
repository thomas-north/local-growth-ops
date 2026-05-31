"""
lead_hub.list_due_followups
~~~~~~~~~~~~~~~~~~~~~~~~~~~
List leads with a follow-up due at or before now.

Usage::

    python3.11 -m lead_hub.list_due_followups <client-slug>

Exits 0 on success (including no results), 1 on error, 2 on usage error.
"""

from __future__ import annotations

import sys

from lead_hub.config_loader import load_client_config
from lead_hub.storage import list_due_followups


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: python3.11 -m lead_hub.list_due_followups <client-slug>",
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
        due = list_due_followups(client_slug)
    except Exception as exc:
        print(f"ERROR: Failed to read leads: {exc}", file=sys.stderr)
        return 1

    if not due:
        print(f"No follow-ups due for {client_slug!r}.")
        return 0

    print(f"Due follow-ups for {client_slug!r} ({len(due)} total):\n")
    for lead in due:
        print(
            f"  {lead.lead_id[:8]}  "
            f"{lead.next_followup_at.strftime('%Y-%m-%d %H:%M UTC')}  "  # type: ignore[union-attr]
            f"{lead.status.value:<22}  "
            f"{lead.name}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
