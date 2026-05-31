"""
lead_hub.schemas.intake
~~~~~~~~~~~~~~~~~~~~~~~
Intake payload schemas and converters.

Two intake paths are supported in this plan:

1. **Website payload** — submitted by the ``local-growth-sites`` contact form.
   ``privacy_accepted`` must be ``true``. The stored ``source`` is
   ``website:<site_id>``.

2. **Manual payload** — created by the operator for testing, pilots, or
   phone/walk-in enquiries. ``privacy_accepted`` defaults to ``false`` and
   ``source`` is always ``"manual"``.

Both paths produce a ``NormalizedLead`` via a converter function. No lead
is stored by these functions; the caller is responsible for calling
``lead_hub.storage.append_lead``.

Website payload contract
------------------------
This schema is the stable contract that ``local-growth-sites`` must emit
from its contact form. See ``docs/website-payload-contract.md`` for the
canonical reference shared with that repo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from lead_hub.schemas.lead import (
    ConsentInfo,
    ContactInfo,
    ContactMethod,
    NormalizedLead,
    Urgency,
    new_lead,
)

# ---------------------------------------------------------------------------
# Website payload
# ---------------------------------------------------------------------------


class WebsiteLeadPayload(BaseModel):
    """Payload emitted by the local-growth-sites contact form."""

    client_id: str
    site_id: str
    source_page: str
    submitted_at: datetime
    name: str
    preferred_contact_method: ContactMethod = ContactMethod.unknown
    email: Optional[str] = None
    phone: Optional[str] = None
    service_requested: str = ""
    urgency: Urgency = Urgency.normal
    message: str
    privacy_accepted: bool
    marketing_opt_in: bool = False

    @field_validator("client_id", "site_id", "source_page", "name", "message")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v

    @field_validator("submitted_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("submitted_at must be a timezone-aware datetime")
        return v

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
    def must_have_contact(self) -> "WebsiteLeadPayload":
        if not self.email and not self.phone:
            raise ValueError(
                "at least one of email or phone must be provided"
            )
        return self

    @model_validator(mode="after")
    def privacy_must_be_accepted(self) -> "WebsiteLeadPayload":
        if not self.privacy_accepted:
            raise ValueError(
                "privacy_accepted must be true for website payloads"
            )
        return self


def website_payload_to_lead(payload: WebsiteLeadPayload) -> NormalizedLead:
    """Convert a validated website payload to a NormalizedLead.

    The ``client_id`` identity check (payload vs. configured client) must be
    performed by the caller before calling this function.
    """
    contact = ContactInfo(
        email=payload.email or None,
        phone=payload.phone or None,
        preferred_method=payload.preferred_contact_method,
    )
    consent = ConsentInfo(
        privacy_accepted=payload.privacy_accepted,
        marketing_opt_in=payload.marketing_opt_in,
    )
    # Override lead_id and received_at via new_lead, but force received_at
    # from submitted_at (may differ from now if payload was delayed).
    lead = new_lead(
        client_id=payload.client_id,
        source=f"website:{payload.site_id}",
        name=payload.name,
        contact=contact,
        message=payload.message,
        service_requested=payload.service_requested,
        urgency=payload.urgency,
        consent=consent,
    )
    # Replace received_at with the form's submitted_at timestamp.
    return lead.model_copy(update={"received_at": payload.submitted_at})


# ---------------------------------------------------------------------------
# Manual payload
# ---------------------------------------------------------------------------


class ManualLeadPayload(BaseModel):
    """Operator-created lead for testing, pilots, or phone/walk-in enquiries."""

    client_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_contact_method: ContactMethod = ContactMethod.unknown
    service_requested: str = ""
    message: str = "Manual test lead — please quote for a job."
    urgency: Urgency = Urgency.normal

    @field_validator("client_id", "name")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v

    @field_validator("message")
    @classmethod
    def message_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v

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
    def must_have_contact(self) -> "ManualLeadPayload":
        if not self.email and not self.phone:
            raise ValueError(
                "at least one of email or phone must be provided"
            )
        return self


def manual_payload_to_lead(payload: ManualLeadPayload) -> NormalizedLead:
    """Convert a validated manual payload to a NormalizedLead.

    Manual leads always have ``source="manual"`` and
    ``consent.privacy_accepted=False``.
    """
    contact = ContactInfo(
        email=payload.email or None,
        phone=payload.phone or None,
        preferred_method=payload.preferred_contact_method,
    )
    consent = ConsentInfo(
        # Manual/operator leads: privacy_accepted=False is documented and acceptable.
        privacy_accepted=False,
        marketing_opt_in=False,
    )
    return new_lead(
        client_id=payload.client_id,
        source="manual",
        name=payload.name,
        contact=contact,
        message=payload.message,
        service_requested=payload.service_requested,
        urgency=payload.urgency,
        consent=consent,
    )
