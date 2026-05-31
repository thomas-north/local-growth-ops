"""
lead_hub.schemas.client_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pydantic v2 schema for the per-client assistant configuration.

Every field documented here is the source of truth for lead classification,
reply drafting, escalation rules, and follow-up scheduling.
"""

import re

from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Permissive email pattern — accepts example/reserved TLDs such as .invalid
# per the plan requirement that example domains are allowed.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_slug(value: str) -> bool:
    return bool(_SLUG_RE.match(value))


def _is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class BusinessConfig(BaseModel):
    name: str
    legal_name: str
    tagline: str = ""
    description: str
    phone: str
    email: str
    address_visible: bool
    area: str

    @field_validator("name", "legal_name", "description", "phone", "area")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        if not _is_email(v):
            raise ValueError(
                f"{v!r} is not a valid email address. "
                "Example domains (e.g. .invalid, .example) are accepted."
            )
        return v


class ServiceConfig(BaseModel):
    name: str
    slug: str

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("service name must not be empty")
        return v

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        if not _is_slug(v):
            raise ValueError(
                f"service slug {v!r} must use lowercase letters, numbers, "
                "and hyphens only (e.g. 'full-rewire')"
            )
        return v


class HoursConfig(BaseModel):
    monday_friday: str
    saturday: str
    sunday: str


class ToneConfig(BaseModel):
    style: str
    length: str
    sign_off: str

    @field_validator("style", "length", "sign_off")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v


class ApprovalConfig(BaseModel):
    # Empty strings are allowed — real values live in secrets outside git.
    telegram_chat_id: str = ""
    email: str = ""


class FollowupConfig(BaseModel):
    first_followup_days: int
    second_followup_days: int
    max_followups: int

    @field_validator("first_followup_days", "second_followup_days")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v

    @field_validator("max_followups")
    @classmethod
    def max_followups_range(cls, v: int) -> int:
        if not (0 <= v <= 5):
            raise ValueError("must be between 0 and 5")
        return v

    @model_validator(mode="after")
    def second_gte_first(self) -> "FollowupConfig":
        if self.second_followup_days < self.first_followup_days:
            raise ValueError(
                "second_followup_days must be >= first_followup_days"
            )
        return self


class AutoSendConfig(BaseModel):
    first_reply: bool
    followups: bool
    weekly_report: bool

    @model_validator(mode="after")
    def mvp_safety_rule(self) -> "AutoSendConfig":
        """MVP: supervised mode only. Auto-send must remain off."""
        if self.first_reply:
            raise ValueError(
                "auto_send.first_reply must be false in the MVP. "
                "All replies require operator approval."
            )
        if self.followups:
            raise ValueError(
                "auto_send.followups must be false in the MVP. "
                "All follow-ups require operator approval."
            )
        return self


class RetentionConfig(BaseModel):
    lead_retention_days: int
    delete_pii_after_days: int

    @field_validator("lead_retention_days", "delete_pii_after_days")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v

    @model_validator(mode="after")
    def pii_gte_lead(self) -> "RetentionConfig":
        if self.delete_pii_after_days < self.lead_retention_days:
            raise ValueError(
                "delete_pii_after_days must be >= lead_retention_days"
            )
        return self


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class ClientAssistantConfig(BaseModel):
    client_id: str
    client_slug: str
    business: BusinessConfig
    services: list[ServiceConfig]
    exclusions: list[str]
    pricing_policy: str
    hours: HoursConfig
    tone: ToneConfig
    approval: ApprovalConfig
    escalation_triggers: list[str]
    followup: FollowupConfig
    auto_send: AutoSendConfig
    retention: RetentionConfig

    # ------------------------------------------------------------------
    # Field validators
    # ------------------------------------------------------------------

    @field_validator("client_id", "client_slug")
    @classmethod
    def must_be_slug(cls, v: str) -> str:
        if not _is_slug(v):
            raise ValueError(
                f"{v!r} must use lowercase letters, numbers, and hyphens only"
            )
        return v

    @field_validator("pricing_policy")
    @classmethod
    def pricing_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("pricing_policy must not be empty")
        return v

    @field_validator("exclusions", "escalation_triggers")
    @classmethod
    def at_least_one(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must contain at least one entry")
        return v

    @field_validator("services")
    @classmethod
    def services_non_empty_unique_slugs(
        cls, v: list[ServiceConfig]
    ) -> list[ServiceConfig]:
        if not v:
            raise ValueError("services must contain at least one service")
        slugs = [s.slug for s in v]
        seen: set[str] = set()
        for slug in slugs:
            if slug in seen:
                raise ValueError(f"duplicate service slug: {slug!r}")
            seen.add(slug)
        return v

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def client_id_matches_slug(self) -> "ClientAssistantConfig":
        if self.client_id != self.client_slug:
            raise ValueError(
                f"client_id {self.client_id!r} must match "
                f"client_slug {self.client_slug!r}"
            )
        return self
