"""
lead_hub.storage
~~~~~~~~~~~~~~~~
JSONL storage helpers for the normalized lead model.

State root resolution
---------------------
Production:  /var/openclaw/clients/<client-slug>/leads.jsonl
Development: set LOCAL_GROWTH_STATE_ROOT=<path> to override.

The canonical path is documented in docs/local-state.md.
State files are never committed to git.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lead_hub.schemas.lead import LeadStatus, NormalizedLead

# ---------------------------------------------------------------------------
# State root
# ---------------------------------------------------------------------------

_DEFAULT_STATE_ROOT = Path("/var/openclaw")
_ENV_KEY = "LOCAL_GROWTH_STATE_ROOT"


def state_root() -> Path:
    """Return the runtime state root, respecting LOCAL_GROWTH_STATE_ROOT."""
    override = os.environ.get(_ENV_KEY)
    if override:
        return Path(override)
    return _DEFAULT_STATE_ROOT


def client_dir(client_slug: str) -> Path:
    """Return (and create if needed) the per-client state directory."""
    path = state_root() / "clients" / client_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def leads_path(client_slug: str) -> Path:
    """Return the JSONL path for a client's leads."""
    return client_dir(client_slug) / "leads.jsonl"


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------


def read_leads(client_slug: str) -> list[NormalizedLead]:
    """Read all leads for a client from JSONL. Returns [] if file is absent."""
    path = leads_path(client_slug)
    if not path.exists():
        return []
    leads: list[NormalizedLead] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            leads.append(NormalizedLead.model_validate_json(line))
    return leads


def _write_leads(client_slug: str, leads: list[NormalizedLead]) -> None:
    """Rewrite the entire leads.jsonl for a client."""
    path = leads_path(client_slug)
    lines = [lead.model_dump_json() for lead in leads]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def append_lead(client_slug: str, lead: NormalizedLead) -> None:
    """Append a single lead to the client's JSONL file."""
    path = leads_path(client_slug)
    with path.open("a", encoding="utf-8") as f:
        f.write(lead.model_dump_json() + "\n")


# ---------------------------------------------------------------------------
# Status updates
# ---------------------------------------------------------------------------


def update_lead_status(
    client_slug: str,
    lead_id: str,
    new_status: LeadStatus,
    next_followup_at: Optional[datetime] = None,
) -> NormalizedLead:
    """Update the status (and optionally follow-up timestamp) of a lead.

    Rewrites the full JSONL file — acceptable for MVP volumes.

    Raises
    ------
    KeyError
        If no lead with *lead_id* exists for *client_slug*.
    """
    leads = read_leads(client_slug)
    updated: Optional[NormalizedLead] = None
    new_leads: list[NormalizedLead] = []

    for lead in leads:
        if lead.lead_id == lead_id:
            updated = lead.model_copy(
                update={
                    "status": new_status,
                    "next_followup_at": next_followup_at
                    if next_followup_at is not None
                    else lead.next_followup_at,
                }
            )
            new_leads.append(updated)
        else:
            new_leads.append(lead)

    if updated is None:
        raise KeyError(
            f"No lead with id {lead_id!r} found for client {client_slug!r}"
        )

    _write_leads(client_slug, new_leads)
    return updated


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_due_followups(
    client_slug: str,
    as_of: Optional[datetime] = None,
) -> list[NormalizedLead]:
    """Return leads with next_followup_at at or before *as_of* (default: now UTC)."""
    now = as_of if as_of is not None else datetime.now(tz=timezone.utc)
    return [
        lead
        for lead in read_leads(client_slug)
        if lead.next_followup_at is not None and lead.next_followup_at <= now
    ]
