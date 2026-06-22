"""
lead_hub.schemas.assistant_workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Output schemas for the follow-up assistant workflow.

These models mirror the required output fields defined in
``openclaw/agents/followup-assistant/prompts/``.  They are intentionally
strict so that the deterministic dry-run and any future live Openclaw
adapter both produce the same validated shape.

No model/API calls happen in this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

from lead_hub.schemas.lead import LeadStatus

# ---------------------------------------------------------------------------
# Classification taxonomy — matches prompts/classify.md
# ---------------------------------------------------------------------------


class Classification(str, Enum):
    genuine_lead = "genuine_lead"
    spam = "spam"
    out_of_scope = "out_of_scope"
    needs_human_review = "needs_human_review"
    complaint_or_dispute = "complaint_or_dispute"
    urgent_or_safety = "urgent_or_safety"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class EscalationSeverity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    none = "none"


# ---------------------------------------------------------------------------
# EscalationCheck — mirrors prompts/escalation.md required output
# ---------------------------------------------------------------------------


class EscalationCheck(BaseModel):
    escalation_required: bool
    severity: EscalationSeverity
    reasons: list[str]
    operator_summary: str
    suggested_operator_action: str

    @model_validator(mode="after")
    def severity_consistent(self) -> "EscalationCheck":
        if not self.escalation_required:
            if self.severity != EscalationSeverity.none:
                raise ValueError(
                    "severity must be 'none' when escalation_required is false"
                )
            if self.reasons:
                raise ValueError(
                    "reasons must be empty when escalation_required is false"
                )
        else:
            if self.severity == EscalationSeverity.none:
                raise ValueError(
                    "severity must not be 'none' when escalation_required is true"
                )
        return self


# ---------------------------------------------------------------------------
# LeadClassification — mirrors prompts/classify.md required output
# ---------------------------------------------------------------------------


class LeadClassification(BaseModel):
    classification: Classification
    confidence: Confidence
    summary: str
    recommended_next_status: LeadStatus
    risk_flags: list[str]
    escalation_required: bool
    escalation_reason: str

    @model_validator(mode="after")
    def escalation_status_consistent(self) -> "LeadClassification":
        if self.escalation_required:
            if self.recommended_next_status != LeadStatus.escalated:
                raise ValueError(
                    "recommended_next_status must be 'escalated' when "
                    "escalation_required is true"
                )
            if not self.escalation_reason:
                raise ValueError(
                    "escalation_reason must not be empty when "
                    "escalation_required is true"
                )
        if self.classification == Classification.spam:
            if self.recommended_next_status != LeadStatus.spam:
                raise ValueError(
                    "recommended_next_status must be 'spam' when "
                    "classification is 'spam'"
                )
        return self


# ---------------------------------------------------------------------------
# DraftReply — mirrors prompts/draft_reply.md required output
# ---------------------------------------------------------------------------


class DraftReply(BaseModel):
    draft_subject: str
    draft_body: str
    assumptions: list[str]
    questions_for_lead: list[str]
    operator_notes: str
    approval_required: Literal[True]  # must always be True — enforced by type

    @field_validator("approval_required")
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("approval_required must always be true in the MVP")
        return v


# ---------------------------------------------------------------------------
# AssistantRun — one persisted record per processed lead
# ---------------------------------------------------------------------------


class AssistantRun(BaseModel):
    """Written to drafts.jsonl for every processed lead."""

    run_id: str
    lead_id: str
    client_id: str
    processed_at: datetime
    adapter: str  # e.g. "dry-run-v1", "openclaw-v1"
    escalation_check: EscalationCheck
    classification: LeadClassification
    draft_reply: Optional[DraftReply] = None
    new_status: LeadStatus

    @field_validator("processed_at")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("processed_at must be timezone-aware")
        return v

    @model_validator(mode="after")
    def draft_only_for_genuine(self) -> "AssistantRun":
        """Spam and escalated leads must not carry a draft reply."""
        if self.new_status in (LeadStatus.spam, LeadStatus.escalated):
            if self.draft_reply is not None:
                raise ValueError(
                    "draft_reply must be None for spam or escalated leads"
                )
        return self


# ---------------------------------------------------------------------------
# AuditEvent — append-only audit log entry
# ---------------------------------------------------------------------------


class AuditEventKind(str, Enum):
    processed = "processed"
    status_changed = "status_changed"
    draft_created = "draft_created"
    escalated = "escalated"
    notification_sent = "notification_sent"
    error = "error"


class AuditEvent(BaseModel):
    """Written to audit.jsonl for every significant action."""

    event_id: str
    lead_id: str
    client_id: str
    kind: AuditEventKind
    occurred_at: datetime
    detail: str
    previous_status: Optional[LeadStatus] = None
    new_status: Optional[LeadStatus] = None

    @field_validator("occurred_at")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return v
