"""
lead_hub.followup_scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic follow-up draft logic for the supervised follow-up workflow.

Generates safe, template-based follow-up drafts for leads that are due a
check-in. All drafts require operator approval. Nothing is sent automatically.

Safety rules enforced here:
- Spam, escalated, closed, won, and lost leads are never given follow-up drafts.
- No invented prices, availability promises, or guarantees.
- approval_required is always True on every draft.
- max_followups from client config is respected.
"""

from __future__ import annotations

import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from lead_hub.assistant import check_escalation
from lead_hub.schemas.assistant_workflow import (
    AssistantRun,
    AuditEvent,
    AuditEventKind,
    Classification,
    Confidence,
    DraftReply,
    EscalationSeverity,
    LeadClassification,
)
from lead_hub.schemas.client_config import ClientAssistantConfig
from lead_hub.schemas.lead import LeadStatus, NormalizedLead

ADAPTER = "followup-dry-run-v1"

# Leads in these statuses must never receive follow-up drafts.
EXCLUDED_STATUSES: frozenset[LeadStatus] = frozenset([
    LeadStatus.spam,
    LeadStatus.escalated,
    LeadStatus.closed,
    LeadStatus.won,
    LeadStatus.lost,
])


# ---------------------------------------------------------------------------
# Audit event counting
# ---------------------------------------------------------------------------


def count_followup_drafts(client_slug: str, lead_id: str) -> int:
    """
    Count how many follow-up drafts have already been generated for a lead.

    Reads followup_draft_created audit events from audit.jsonl. Used to
    determine whether the lead is on its 1st, 2nd, etc. follow-up, and
    whether max_followups has been reached.
    """
    from lead_hub.storage import read_audit_events
    events = read_audit_events(client_slug)
    return sum(
        1 for e in events
        if e.lead_id == lead_id and e.kind == AuditEventKind.followup_draft_created
    )


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def compute_next_followup_at(
    config: ClientAssistantConfig,
    lead_received_at: datetime,
    followup_number: int,
) -> Optional[datetime]:
    """
    Return the datetime for the next scheduled follow-up after this one,
    or None if max_followups has been reached.

    followup_number is the number of follow-ups that will exist AFTER the
    current one is generated (i.e. 1 after first draft, 2 after second).

    Cadence is relative to lead received_at to keep scheduling deterministic.
    """
    fc = config.followup
    if followup_number >= fc.max_followups:
        return None
    if followup_number == 0:
        return lead_received_at + timedelta(days=fc.first_followup_days)
    if followup_number == 1:
        return lead_received_at + timedelta(days=fc.second_followup_days)
    # Beyond two configured slots: no further follow-up
    return None


# ---------------------------------------------------------------------------
# Draft generation
# ---------------------------------------------------------------------------


def build_followup_draft(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
    followup_number: int,
) -> DraftReply:
    """
    Build a safe, template-based follow-up draft for a lead.

    Rules enforced:
    - No invented prices.
    - No promises of availability, dates, or outcomes.
    - Uses config tone and sign_off.
    - approval_required is always True.
    """
    biz = config.business
    tone = config.tone

    service_line = f" about your {lead.service_requested} enquiry" if lead.service_requested else ""
    contact_hint = biz.phone if biz.phone else "our contact form"
    first_name = lead.name.split()[0]

    if followup_number == 0:
        opening = (
            f"Hi {first_name},\n\n"
            f"I just wanted to follow up on the message you sent us{service_line}. "
            "We haven't heard back yet and wanted to make sure our reply reached you.\n\n"
            f"If you'd like to arrange a quick call to discuss the job, please ring us on {contact_hint}."
        )
        subject_suffix = "Following up on your enquiry"
    else:
        opening = (
            f"Hi {first_name},\n\n"
            f"I'm reaching out one final time regarding your enquiry{service_line}. "
            "If you've already found someone or the timing isn't right, no problem at all "
            "-- just let us know and we'll close this off.\n\n"
            f"Otherwise, we're still happy to help. Feel free to ring us on {contact_hint}."
        )
        subject_suffix = "Final follow-up"

    body = textwrap.dedent(f"""\
        {opening}

        {tone.sign_off}""")

    return DraftReply(
        draft_subject=f"{subject_suffix} -- {biz.name}",
        draft_body=body,
        assumptions=[
            f"Follow-up number: {followup_number + 1}",
            "Lead has not replied since initial enquiry",
        ],
        questions_for_lead=[],
        operator_notes=(
            f"Follow-up {followup_number + 1} of {config.followup.max_followups}. "
            f"Review tone ({tone.style!r}) and confirm phone ({contact_hint}) before sending."
        ),
        approval_required=True,
    )


# ---------------------------------------------------------------------------
# Top-level workflow
# ---------------------------------------------------------------------------


def run_followup_workflow(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
    followup_count: int,
) -> AssistantRun:
    """
    Run the follow-up draft workflow for a single due lead.

    followup_count is the number of follow-up drafts already generated for
    this lead (from count_followup_drafts). The new draft will be
    followup_count + 1 overall.

    Returns an AssistantRun record ready to persist. Caller handles storage.
    """
    now = datetime.now(tz=timezone.utc)

    # Always run the escalation check -- a lead may have had a complaint added
    # to its conversation_summary since the original classification.
    escalation = check_escalation(lead, config)

    if escalation.escalation_required:
        # Safety: do not draft a follow-up for an escalated lead even if it
        # slipped through the status filter. Produce a no-draft run.
        classification = LeadClassification(
            classification=Classification.complaint_or_dispute,
            confidence=Confidence.high,
            summary="Escalation detected during follow-up check; no draft produced.",
            recommended_next_status=LeadStatus.escalated,
            risk_flags=escalation.reasons,
            escalation_required=True,
            escalation_reason=escalation.reasons[0] if escalation.reasons else "escalation trigger",
        )
        return AssistantRun(
            run_id=str(uuid.uuid4()),
            lead_id=lead.lead_id,
            client_id=config.client_id,
            processed_at=now,
            adapter=ADAPTER,
            escalation_check=escalation,
            classification=classification,
            draft_reply=None,
            new_status=LeadStatus.escalated,
        )

    draft = build_followup_draft(lead, config, followup_count)

    classification = LeadClassification(
        classification=Classification.genuine_lead,
        confidence=Confidence.high,
        summary=f"Follow-up {followup_count + 1} draft produced.",
        recommended_next_status=LeadStatus.followup_scheduled,
        risk_flags=[],
        escalation_required=False,
        escalation_reason="",
    )

    return AssistantRun(
        run_id=str(uuid.uuid4()),
        lead_id=lead.lead_id,
        client_id=config.client_id,
        processed_at=now,
        adapter=ADAPTER,
        escalation_check=escalation,
        classification=classification,
        draft_reply=draft,
        new_status=LeadStatus.followup_scheduled,
    )


def make_followup_audit_event(
    lead: NormalizedLead,
    run: AssistantRun,
    previous_status: LeadStatus,
    followup_number: int,
) -> AuditEvent:
    """Create an AuditEvent for a follow-up draft action."""
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        lead_id=lead.lead_id,
        client_id=run.client_id,
        kind=AuditEventKind.followup_draft_created,
        occurred_at=run.processed_at,
        detail=f"Follow-up {followup_number + 1} draft created by {run.adapter}; approval required.",
        previous_status=previous_status,
        new_status=run.new_status,
    )
