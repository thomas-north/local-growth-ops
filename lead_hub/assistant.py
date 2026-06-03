"""
lead_hub.assistant
~~~~~~~~~~~~~~~~~~
Deterministic dry-run assistant logic for the follow-up assistant workflow.

This module implements the classification and safe draft reply steps using
keyword heuristics and templates. It produces outputs that match the exact
schemas defined in ``lead_hub.schemas.assistant_workflow`` and the prompt
output shapes defined in ``openclaw/agents/followup-assistant/prompts/``.

No model/API/Openclaw calls are made. The adapter string is ``"dry-run-v1"``.

When a live Openclaw adapter is connected in a later plan, it will replace
the ``classify_lead`` and ``draft_reply`` functions below with an adapter
that calls the actual model, but produces the same validated schema objects.

Safety posture
--------------
- Bias toward escalation. Any ambiguity → ``needs_human_review`` or escalate.
- No draft reply for escalated, spam, or out-of-scope leads.
- ``approval_required`` is always ``True`` on every draft.
- No invented prices, availability promises, or guarantees in drafts.
"""

from __future__ import annotations

import re
import textwrap
import uuid
from datetime import datetime, timezone

from lead_hub.schemas.assistant_workflow import (
    AssistantRun,
    AuditEvent,
    AuditEventKind,
    Classification,
    Confidence,
    DraftReply,
    EscalationCheck,
    EscalationSeverity,
    LeadClassification,
)
from lead_hub.schemas.client_config import ClientAssistantConfig
from lead_hub.schemas.lead import LeadStatus, NormalizedLead

ADAPTER = "dry-run-v1"

# ---------------------------------------------------------------------------
# Keyword sets for dry-run heuristics
# ---------------------------------------------------------------------------

_ESCALATION_KEYWORDS = frozenset([
    "complaint", "complain", "dispute", "refund", "compensation",
    "taking this further", "legal", "lawyer", "solicitor", "insurance",
    # "guarantee"/"guaranteed" intentionally excluded here: they appear in
    # spam phrases like "guaranteed leads SEO" and are handled by the
    # config escalation_trigger "request for written guarantee or contract".
    "warranty", "court", "trading standards",
    "threatening", "abusive", "abuse", "harassment",
    "safety hazard", "dangerous", "risk to life", "gas leak",
    "electric shock", "urgent hazard",
    "distress", "crisis",
])

_SPAM_KEYWORDS = frozenset([
    "seo", "backlink", "crypto", "bitcoin", "investment opportunity",
    "click here", "unsubscribe", "marketing agency", "guaranteed leads",
    "we can rank", "first page of google", "limited time offer",
    "make money", "work from home", "dear friend", "congratulations you",
])

_PRICE_PATTERNS = [
    re.compile(r"£\s*\d+"),          # £300
    re.compile(r"\d+\s*pounds?"),     # 300 pounds
    re.compile(r"costs?\s+£"),        # costs £
    re.compile(r"quote\s+of\s+£"),    # quote of £
    re.compile(r"price\s+of\s+£"),    # price of £
]


def _lower_tokens(text: str) -> set[str]:
    """Return lowercased words and common phrases from text."""
    t = text.lower()
    return set(re.split(r"[\s,\.;:!?\"']+", t))


def _contains_escalation(text: str) -> tuple[bool, list[str]]:
    tokens = _lower_tokens(text)
    tl = text.lower()
    matched = [kw for kw in _ESCALATION_KEYWORDS if kw in tl]
    return bool(matched), matched


def _contains_spam(text: str) -> bool:
    tl = text.lower()
    return any(kw in tl for kw in _SPAM_KEYWORDS)


def _contains_invented_price(text: str) -> bool:
    return any(p.search(text) for p in _PRICE_PATTERNS)


def _is_in_scope(lead: NormalizedLead, config: ClientAssistantConfig) -> bool:
    """Return True if the service request matches a configured service."""
    if not lead.service_requested:
        return True  # no specific service → treat as general enquiry, not out-of-scope
    req = lead.service_requested.lower()
    for svc in config.services:
        if req == svc.slug.lower() or req in svc.name.lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Escalation check
# ---------------------------------------------------------------------------


def check_escalation(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
) -> EscalationCheck:
    """Pre-flight escalation check based on lead message and config triggers."""
    combined = f"{lead.message} {lead.conversation_summary}"
    escalated, matched_keywords = _contains_escalation(combined)

    # Also check config escalation_triggers
    tl = combined.lower()
    config_triggers = [t for t in config.escalation_triggers if t.lower() in tl]

    all_reasons = list(dict.fromkeys(matched_keywords + config_triggers))  # dedup, order-preserving

    if not escalated and not config_triggers:
        return EscalationCheck(
            escalation_required=False,
            severity=EscalationSeverity.none,
            reasons=[],
            operator_summary="",
            suggested_operator_action="",
        )

    # Determine severity
    critical_kws = {"gas leak", "electric shock", "fire", "risk to life", "emergency",
                    "threatening", "abusive", "abuse"}
    high_kws = {"complaint", "complain", "dispute", "refund", "compensation",
                "legal", "lawyer", "solicitor", "court", "insurance", "warranty", "guarantee"}
    if any(k in tl for k in critical_kws):
        severity = EscalationSeverity.critical
    elif any(k in tl for k in high_kws):
        severity = EscalationSeverity.high
    else:
        severity = EscalationSeverity.medium

    return EscalationCheck(
        escalation_required=True,
        severity=severity,
        reasons=all_reasons[:5],  # cap for readability
        operator_summary=(
            f"Lead from {lead.name!r} triggers escalation. "
            f"Detected: {', '.join(all_reasons[:3])}. "
            "Do not draft a reply without operator review."
        ),
        suggested_operator_action=(
            "Review the lead message directly. If it relates to past work or "
            "a complaint, escalate to the business owner before any response."
        ),
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_lead(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
    escalation: EscalationCheck,
) -> LeadClassification:
    """Deterministic classification using keyword heuristics."""
    text = f"{lead.message} {lead.conversation_summary}"

    # Escalation takes priority
    if escalation.escalation_required:
        tl = text.lower()
        if any(k in tl for k in {"safety", "hazard", "gas leak", "electric shock",
                                   "fire", "risk to life", "emergency", "urgent hazard"}):
            cat = Classification.urgent_or_safety
        else:
            cat = Classification.complaint_or_dispute
        return LeadClassification(
            classification=cat,
            confidence=Confidence.high,
            summary=f"Escalation required: {', '.join(escalation.reasons[:2])}.",
            recommended_next_status=LeadStatus.escalated,
            risk_flags=escalation.reasons,
            escalation_required=True,
            escalation_reason=escalation.reasons[0] if escalation.reasons else "escalation trigger detected",
        )

    # Spam
    if _contains_spam(text):
        return LeadClassification(
            classification=Classification.spam,
            confidence=Confidence.high,
            summary="Message matches spam/marketing patterns.",
            recommended_next_status=LeadStatus.spam,
            risk_flags=["spam_keywords_detected"],
            escalation_required=False,
            escalation_reason="",
        )

    # Out-of-scope
    if not _is_in_scope(lead, config):
        return LeadClassification(
            classification=Classification.out_of_scope,
            confidence=Confidence.medium,
            summary=(
                f"Service requested ({lead.service_requested!r}) does not match "
                "any configured service. Needs human review."
            ),
            recommended_next_status=LeadStatus.escalated,
            risk_flags=["out_of_scope_service"],
            escalation_required=True,
            escalation_reason=f"Requested service {lead.service_requested!r} is not in the configured service list.",
        )

    # Genuine in-scope lead
    service_label = lead.service_requested or "general enquiry"
    return LeadClassification(
        classification=Classification.genuine_lead,
        confidence=Confidence.medium,
        summary=f"In-scope enquiry for {service_label}. Ready for reply draft.",
        recommended_next_status=LeadStatus.awaiting_approval,
        risk_flags=[],
        escalation_required=False,
        escalation_reason="",
    )


# ---------------------------------------------------------------------------
# Draft reply
# ---------------------------------------------------------------------------


def build_draft_reply(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
) -> DraftReply:
    """
    Build a safe, template-based draft reply for a genuine in-scope lead.

    Rules enforced:
    - No invented prices.
    - No promises of availability, dates, or outcomes.
    - Uses config tone.style, tone.length, and tone.sign_off.
    - approval_required is always True.
    """
    biz = config.business
    tone = config.tone

    # Resolve service name from slug or use raw value
    service_name = lead.service_requested
    for svc in config.services:
        if lead.service_requested and (
            lead.service_requested.lower() == svc.slug.lower()
            or lead.service_requested.lower() in svc.name.lower()
        ):
            service_name = svc.name
            break

    service_line = f" for a {service_name}" if service_name else ""
    contact_hint = biz.phone if biz.phone else "our contact form"

    body = textwrap.dedent(f"""\
        Hi {lead.name.split()[0]},

        Thank you for getting in touch. We'd be happy to help with your enquiry{service_line}.

        To give you an accurate quote we'd need to find out a bit more about the job. \
Could you let us know a convenient time to call, or feel free to ring us on {contact_hint}?

        {tone.sign_off}""")

    assumptions = []
    if lead.service_requested:
        assumptions.append(f"Service interpreted as: {service_name}")
    assumptions.append("Property assumed domestic/residential — not commercial")

    return DraftReply(
        draft_subject=f"Re: Your enquiry — {biz.name}",
        draft_body=body,
        assumptions=assumptions,
        questions_for_lead=[
            "What is the size / number of circuits or bedrooms in the property?",
            "Is there an existing report, or is this the first inspection?",
        ],
        operator_notes=(
            f"Dry-run draft. Review tone ({tone.style!r}) and confirm phone number "
            f"({contact_hint}) before sending. No pricing quoted."
        ),
        approval_required=True,
    )


# ---------------------------------------------------------------------------
# Top-level workflow
# ---------------------------------------------------------------------------


def run_workflow(
    lead: NormalizedLead,
    config: ClientAssistantConfig,
) -> AssistantRun:
    """
    Run the full dry-run workflow for a single lead.

    Returns an AssistantRun record ready to be persisted. Does not write to
    storage — the caller is responsible for that.
    """
    now = datetime.now(tz=timezone.utc)

    escalation = check_escalation(lead, config)
    classification = classify_lead(lead, config, escalation)

    draft: DraftReply | None = None
    if (
        classification.classification == Classification.genuine_lead
        and not escalation.escalation_required
    ):
        draft = build_draft_reply(lead, config)

    new_status = classification.recommended_next_status

    return AssistantRun(
        run_id=str(uuid.uuid4()),
        lead_id=lead.lead_id,
        client_id=config.client_id,
        processed_at=now,
        adapter=ADAPTER,
        escalation_check=escalation,
        classification=classification,
        draft_reply=draft,
        new_status=new_status,
    )


def make_audit_event(
    lead: NormalizedLead,
    run: AssistantRun,
    previous_status: LeadStatus,
) -> AuditEvent:
    """Create an AuditEvent summarising what the workflow did to a lead."""
    if run.new_status == LeadStatus.escalated:
        kind = AuditEventKind.escalated
        detail = f"Escalated: {run.classification.escalation_reason}"
    elif run.draft_reply is not None:
        kind = AuditEventKind.draft_created
        detail = f"Draft created by {run.adapter}; approval required."
    else:
        kind = AuditEventKind.processed
        detail = f"Processed by {run.adapter}; classification={run.classification.classification.value}."

    return AuditEvent(
        event_id=str(uuid.uuid4()),
        lead_id=lead.lead_id,
        client_id=run.client_id,
        kind=kind,
        occurred_at=run.processed_at,
        detail=detail,
        previous_status=previous_status,
        new_status=run.new_status,
    )
