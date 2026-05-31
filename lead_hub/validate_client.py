"""
lead_hub.validate_client
~~~~~~~~~~~~~~~~~~~~~~~~
CLI entry point for validating a client assistant config.

Usage::

    python3 -m lead_hub.validate_client <client-slug>

Exits 0 on success, 1 on validation error, 2 on usage error.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError

from lead_hub.config_loader import load_client_config


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: python3 -m lead_hub.validate_client <client-slug>",
            file=sys.stderr,
        )
        return 2

    client_slug = args[0]

    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(
            f"Config validation failed for {client_slug!r}:\n",
            file=sys.stderr,
        )
        for error in exc.errors():
            loc = " -> ".join(str(p) for p in error["loc"])
            print(f"  [{loc}] {error['msg']}", file=sys.stderr)
        return 1

    print(
        f"OK: {client_slug!r} config is valid "
        f"({config.business.name}, {len(config.services)} service(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
