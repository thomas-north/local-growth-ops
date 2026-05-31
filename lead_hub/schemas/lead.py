"""
lead_hub.schemas.lead
~~~~~~~~~~~~~~~~~~~~~
Normalized lead model and status enum.

Every lead that enters the system is stored as a NormalizedLead record.
Deterministic lead handling (storage, status transitions) lives in
lead_hub.storage. Judgment-based work (drafting, classification) lives in
the Openclaw agent layer.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]*$")


def _non_empty(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("must not be empty or whitespace")
    return v


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LeadStatus(str, Enum):
    new = "new"
    needs_reply_draft = "needs_reply_draft"
    awaiting_approval = "awaiting_approval"
    replied = "replied"
    followup_scheduled = "followup_scheduled"
    won = "won"
    lost = "lost"
    spam = "spam"
    escalated = "escalated"
    closed = "closed"


class ContactMethod(str, Enum):
    email = "email"
    phone = "phone"
    sms = "sms"
    whatsapp = "whatsapp"
    unknown = "unknown"


class Urgency(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_method: ContactMethod = ContactMethod.unknown

    @field_validator("email")
    @classmethod
    def email_non_empty_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("email must not be blank if provided")
        return v

    @field_validator("phone")
    @classmethod
    def phone_non_empty_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("phone must not be blank if provided")
        return v

    @model_validator(mode="after")
    def at_least_one_contact(self) -> "ContactInfo":
        if not self.email and not self.phone:
            raise ValueError(
                "at least one of contact.email or contact.phone must be provided"
            )
        return self


class ConsentInfo(BaseModel):
    # MVP: manual test leads may use False with an explicit note.
    # Production intake (plan 0004) must enforce True.
    privacy_accepted: bool = False
    marketing_opt_in: bool = False


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class NormalizedLead(BaseModel):
    lead_id: str
    client_id: str
    source: str
    name: str
    contact: ContactInfo
    message: str
    service_requested: str = ""
    urgency: Urgency = Urgency.normal
    consent: ConsentInfo
    received_at: datetime
    status: LeadStatus = LeadStatus.new
    next_followup_at: Optional[datetime] = None
    assigned_owner: str = ""
    conversation_summary: str = ""

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    @field_validator("lead_id", "client_id")
    @classmethod
    def must_be_slug_like(cls, v: str) -> str:
        if not v or not _SLUG_RE.match(v):
            raise ValueError(
                f"{v!r} must be a non-empty slug-like ID "
                "(letters, numbers, hyphens, underscores; must start with letter or digit)"
            )
        return v

    @field_validator("source", "name", "message")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        return _non_empty(v)

    @field_validator("received_at")
    @classmethod
    def received_at_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("received_at must be a timezone-aware datetime")
        return v

    @field_validator("next_followup_at")
    @classmethod
    def followup_at_must_be_aware_if_set(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            raise ValueError("next_followup_at must be a timezone-aware datetime if provided")
        return v


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def new_lead(
    *,
    client_id: str,
    source: str,
    name: str,
    contact: ContactInfo,
    message: str,
    service_requested: str = "",
    urgency: Urgency = Urgency.normal,
    consent: ConsentInfo,
    next_followup_at: Optional[datetime] = None,
    assigned_owner: str = "",
) -> NormalizedLead:
    """Create a new lead with a generated ID and current UTC timestamp."""
    return NormalizedLead(
        lead_id=str(uuid.uuid4()),
        client_id=client_id,
        source=source,
        name=name,
        contact=contact,
        message=message,
        service_requested=service_requested,
        urgency=urgency,
        consent=consent,
        received_at=datetime.now(tz=timezone.utc),
        status=LeadStatus.new,
        next_followup_at=next_followup_at,
        assigned_owner=assigned_owner,
    )
