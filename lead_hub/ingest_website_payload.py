"""
lead_hub.ingest_website_payload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ingest a website form payload JSON file into the lead hub.

Usage::

    python3.11 -m lead_hub.ingest_website_payload <client-slug> <payload.json>

The payload file must be a JSON object matching the WebsiteLeadPayload
contract (see docs/website-payload-contract.md).

Validation performed:
- client config must exist and be valid
- payload must parse and pass schema validation
- payload client_id must match the command's client-slug argument
- privacy_accepted must be true

Exits 0 on success, 1 on validation/IO error, 2 on usage error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from lead_hub.config_loader import load_client_config
from lead_hub.schemas.intake import WebsiteLeadPayload, website_payload_to_lead
from lead_hub.storage import append_lead


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if len(args) < 2:
        print(
            "Usage: python3.11 -m lead_hub.ingest_website_payload"
            " <client-slug> <payload.json>",
            file=sys.stderr,
        )
        return 2

    client_slug, payload_path_str = args[0], args[1]
    payload_path = Path(payload_path_str)

    # 1. Validate client config.
    try:
        config = load_client_config(client_slug)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # 2. Read payload file.
    if not payload_path.exists():
        print(f"ERROR: payload file not found: {payload_path}", file=sys.stderr)
        return 1
    try:
        raw = payload_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: failed to read payload: {exc}", file=sys.stderr)
        return 1

    # 3. Validate payload schema.
    try:
        payload = WebsiteLeadPayload.model_validate(data)
    except ValidationError as exc:
        print("ERROR: payload validation failed:\n", file=sys.stderr)
        for error in exc.errors():
            loc = " -> ".join(str(p) for p in error["loc"])
            print(f"  [{loc}] {error['msg']}", file=sys.stderr)
        return 1

    # 4. Enforce client_id identity: payload must name the same client as the
    #    command argument.
    if payload.client_id != config.client_id:
        print(
            f"ERROR: client_id mismatch — command client is {client_slug!r} "
            f"but payload.client_id is {payload.client_id!r}",
            file=sys.stderr,
        )
        return 1

    # 5. Convert and store.
    lead = website_payload_to_lead(payload)
    try:
        append_lead(client_slug, lead)
    except Exception as exc:
        print(f"ERROR: failed to store lead: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: lead {lead.lead_id} ingested for {client_slug!r} "
        f"(source={lead.source}, status={lead.status.value})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
