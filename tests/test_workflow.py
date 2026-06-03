"""
tests/test_workflow.py
~~~~~~~~~~~~~~~~~~~~~~
Tests for the lead classification and draft reply workflow.

All data is fictional. Tests use LOCAL_GROWTH_STATE_ROOT via monkeypatch.
No Openclaw, OpenAI, or network calls are made.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_hub.assistant import (
    _contains_invented_price,
    build_draft_reply,
    check_escalation,
    classify_lead,
    make_audit_event,
    run_workflow,
)
from lead_hub.schemas.assistant_workflow import (
    AuditEventKind,
    Classification,
    DraftReply,
    EscalationSeverity,
    LeadStatus,
)
from lead_hub.schemas.client_config import ClientAssistantConfig
from lead_hub.schemas.lead import (
    ConsentInfo,
    ContactInfo,
    LeadStatus as LeadStatusEnum,
    NormalizedLead,
    Urgency,
    new_lead,
)
from lead_hub.storage import (
    append_lead,
    read_assistant_runs,
    read_audit_events,
    read_leads,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 2, 10, 0, 0, tzinfo=timezone.utc)

_CONFIG_DATA = {
    "client_id": "example-client",
    "client_slug": "example-client",
    "business": {
        "name": "Bright Spark Electrical",
        "legal_name": "Bright Spark Electrical Ltd",
        "tagline": "Reliable domestic electricians in South Leeds",
        "description": "A fictional electrical contractor for testing.",
        "phone": "0113 000 0000",
        "email": "hello@example-client.invalid",
        "address_visible": False,
        "area": "South Leeds and surrounding postcodes",
    },
    "services": [
        {"name": "Full rewire", "slug": "full-rewire"},
        {"name": "Consumer unit replacement", "slug": "consumer-unit"},
        {"name": "Fault finding and repair", "slug": "fault-finding"},
        {"name": "Landlord electrical certificate (EICR)", "slug": "eicr"},
        {"name": "EV charger installation", "slug": "ev-charger"},
    ],
    "exclusions": ["Never quote fixed prices without owner approval"],
    "pricing_policy": "Do not quote specific prices.",
    "hours": {"monday_friday": "08:00–18:00", "saturday": "09:00–13:00", "sunday": "Closed"},
    "tone": {
        "style": "Friendly, plain-English, no jargon",
        "length": "Two to three short paragraphs",
        "sign_off": "Tom, Bright Spark Electrical",
    },
    "approval": {"telegram_chat_id": "", "email": ""},
    "escalation_triggers": [
        "complaint or dispute",
        "safety concern or urgent hazard",
        "request for written guarantee or contract",
        "legal or insurance query",
        "abusive or distressing message",
    ],
    "followup": {"first_followup_days": 3, "second_followup_days": 7, "max_followups": 2},
    "auto_send": {"first_reply": False, "followups": False, "weekly_report": False},
    "retention": {"lead_retention_days": 365, "delete_pii_after_days": 730},
}


@pytest.fixture()
def config() -> ClientAssistantConfig:
    return ClientAssistantConfig.model_validate(_CONFIG_DATA)


@pytest.fixture()
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_GROWTH_STATE_ROOT", str(tmp_path))
    return tmp_path


def _make_lead(
    message: str = "Please quote for an EICR.",
    service: str = "eicr",
    name: str = "Jane Smith",
    urgency: Urgency = Urgency.normal,
    conversation_summary: str = "",
) -> NormalizedLead:
    return new_lead(
        client_id="example-client",
        source="manual",
        name=name,
        contact=ContactInfo(email="jane@example.invalid"),
        message=message,
        service_requested=service,
        urgency=urgency,
        consent=ConsentInfo(privacy_accepted=False),
        next_followup_at=None,
    )


# ---------------------------------------------------------------------------
# EscalationCheck
# ---------------------------------------------------------------------------


class TestEscalationCheck:
    def test_clean_lead_no_escalation(self, config):
        lead = _make_lead("Please quote for an EICR.")
        result = check_escalation(lead, config)
        assert not result.escalation_required
        assert result.severity == EscalationSeverity.none
        assert result.reasons == []

    def test_complaint_keyword_escalates(self, config):
        lead = _make_lead("I want to complain about the work done last month.")
        result = check_escalation(lead, config)
        assert result.escalation_required
        assert result.severity in (EscalationSeverity.high, EscalationSeverity.critical)

    def test_safety_keyword_escalates(self, config):
        lead = _make_lead("There is a safety hazard in my property.")
        result = check_escalation(lead, config)
        assert result.escalation_required

    def test_legal_keyword_escalates(self, config):
        lead = _make_lead("I may need to speak to a solicitor about this.")
        result = check_escalation(lead, config)
        assert result.escalation_required

    def test_config_trigger_match_escalates(self, config):
        lead = _make_lead("I have a complaint or dispute about a previous job.")
        result = check_escalation(lead, config)
        assert result.escalation_required

    def test_electric_shock_is_critical(self, config):
        lead = _make_lead("There was an electric shock from the socket.", urgency=Urgency.urgent)
        result = check_escalation(lead, config)
        assert result.escalation_required
        assert result.severity == EscalationSeverity.critical


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_genuine_lead_classified(self, config):
        lead = _make_lead("I need an EICR for my rental property.")
        esc = check_escalation(lead, config)
        result = classify_lead(lead, config, esc)
        assert result.classification == Classification.genuine_lead
        assert result.recommended_next_status == LeadStatus.awaiting_approval
        assert not result.escalation_required

    def test_complaint_classified_as_dispute(self, config):
        lead = _make_lead("I want a refund for the work done last week.")
        esc = check_escalation(lead, config)
        result = classify_lead(lead, config, esc)
        assert result.classification in (
            Classification.complaint_or_dispute, Classification.urgent_or_safety
        )
        assert result.escalation_required
        assert result.recommended_next_status == LeadStatus.escalated

    def test_spam_classified(self, config):
        lead = _make_lead(
            "We can get your website to the first page of google guaranteed leads SEO.",
            service="",
        )
        esc = check_escalation(lead, config)
        result = classify_lead(lead, config, esc)
        assert result.classification == Classification.spam
        assert result.recommended_next_status == LeadStatus.spam

    def test_out_of_scope_classified(self, config):
        lead = _make_lead("Can you fix my boiler?", service="boiler-repair")
        esc = check_escalation(lead, config)
        result = classify_lead(lead, config, esc)
        assert result.classification == Classification.out_of_scope
        assert result.escalation_required
        assert result.recommended_next_status == LeadStatus.escalated

    def test_escalated_has_reason(self, config):
        lead = _make_lead("I want a refund immediately or I'll call trading standards.")
        esc = check_escalation(lead, config)
        result = classify_lead(lead, config, esc)
        assert result.escalation_required
        assert result.escalation_reason  # not empty


# ---------------------------------------------------------------------------
# Draft reply
# ---------------------------------------------------------------------------


class TestDraftReply:
    def test_draft_produced_for_genuine_lead(self, config):
        lead = _make_lead("I need an EICR for my property in Beeston.")
        draft = build_draft_reply(lead, config)
        assert draft.approval_required is True
        assert draft.draft_body
        assert draft.draft_subject

    def test_sign_off_in_draft(self, config):
        lead = _make_lead("I need an EICR.")
        draft = build_draft_reply(lead, config)
        assert "Tom, Bright Spark Electrical" in draft.draft_body

    def test_no_invented_price_in_draft(self, config):
        lead = _make_lead("How much does an EICR cost?", service="eicr")
        draft = build_draft_reply(lead, config)
        assert not _contains_invented_price(draft.draft_body), (
            "Draft body should not contain an invented fixed price"
        )

    def test_no_availability_promise_in_draft(self, config):
        body = build_draft_reply(_make_lead(), config).draft_body.lower()
        forbidden = ["available tomorrow", "available on", "we can come"]
        for phrase in forbidden:
            assert phrase not in body, f"Draft must not promise availability: {phrase!r}"

    def test_approval_required_always_true(self, config):
        draft = build_draft_reply(_make_lead(), config)
        assert draft.approval_required is True

    def test_operator_notes_present(self, config):
        draft = build_draft_reply(_make_lead(), config)
        assert draft.operator_notes


# ---------------------------------------------------------------------------
# DraftReply schema safety enforcement
# ---------------------------------------------------------------------------


class TestDraftReplySchema:
    def test_approval_required_false_rejected(self):
        with pytest.raises(Exception):
            DraftReply(
                draft_subject="Test",
                draft_body="Hi",
                assumptions=[],
                questions_for_lead=[],
                operator_notes="",
                approval_required=False,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Full workflow (run_workflow)
# ---------------------------------------------------------------------------


class TestRunWorkflow:
    def test_genuine_lead_produces_draft(self, config):
        lead = _make_lead("Please quote for an EICR.")
        run = run_workflow(lead, config)
        assert run.draft_reply is not None
        assert run.new_status == LeadStatus.awaiting_approval

    def test_complaint_produces_no_draft(self, config):
        lead = _make_lead("I want to complain about the job.")
        run = run_workflow(lead, config)
        assert run.draft_reply is None
        assert run.new_status == LeadStatus.escalated

    def test_spam_produces_no_draft(self, config):
        lead = _make_lead(
            "We can rank your site on the first page of google guaranteed leads.",
            service="",
        )
        run = run_workflow(lead, config)
        assert run.draft_reply is None
        assert run.new_status == LeadStatus.spam

    def test_out_of_scope_produces_no_draft(self, config):
        lead = _make_lead("Can you fix my plumbing?", service="plumbing")
        run = run_workflow(lead, config)
        assert run.draft_reply is None
        assert run.new_status == LeadStatus.escalated

    def test_run_adapter_is_dry_run(self, config):
        lead = _make_lead()
        run = run_workflow(lead, config)
        assert run.adapter == "dry-run-v1"

    def test_approval_always_required_in_draft(self, config):
        lead = _make_lead("I'd like an EV charger installed.", service="ev-charger")
        run = run_workflow(lead, config)
        assert run.draft_reply is not None
        assert run.draft_reply.approval_required is True

    def test_no_real_client_data_in_output(self, config):
        lead = _make_lead()
        run = run_workflow(lead, config)
        output_json = run.model_dump_json()
        for domain in ("@gmail.com", "@hotmail.com", "@yahoo.com"):
            assert domain not in output_json


# ---------------------------------------------------------------------------
# Storage: drafts and audit files written under LOCAL_GROWTH_STATE_ROOT
# ---------------------------------------------------------------------------


class TestWorkflowStorage:
    def test_drafts_jsonl_written(self, config, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        run = run_workflow(lead, config)

        from lead_hub.storage import append_assistant_run
        append_assistant_run("example-client", run)

        runs = read_assistant_runs("example-client")
        assert len(runs) == 1
        assert runs[0].lead_id == lead.lead_id

    def test_audit_jsonl_written(self, config, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        run = run_workflow(lead, config)
        event = make_audit_event(lead, run, lead.status)

        from lead_hub.storage import append_audit_event
        append_audit_event("example-client", event)

        events = read_audit_events("example-client")
        assert len(events) == 1
        assert events[0].lead_id == lead.lead_id

    def test_drafts_and_audit_in_state_root(self, config, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        run = run_workflow(lead, config)
        event = make_audit_event(lead, run, lead.status)

        from lead_hub.storage import append_assistant_run, append_audit_event, drafts_path, audit_path
        append_assistant_run("example-client", run)
        append_audit_event("example-client", event)

        assert drafts_path("example-client").parent.is_relative_to(tmp_state)
        assert audit_path("example-client").parent.is_relative_to(tmp_state)


# ---------------------------------------------------------------------------
# process_lead CLI
# ---------------------------------------------------------------------------


class TestProcessLeadCLI:
    def test_processes_lead_and_updates_status(self, tmp_state, config):
        from lead_hub.process_lead import main
        lead = _make_lead("I need an EICR.")
        append_lead("example-client", lead)

        rc = main(["example-client", lead.lead_id, "--dry-run"])
        assert rc == 0

        updated = read_leads("example-client")[0]
        assert updated.status != LeadStatus.new

    def test_missing_lead_id_exits_one(self, tmp_state):
        from lead_hub.process_lead import main
        rc = main(["example-client", "no-such-id", "--dry-run"])
        assert rc == 1

    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.process_lead import main
        rc = main([])
        assert rc == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.process_lead import main
        rc = main(["no-such-client", "abc123", "--dry-run"])
        assert rc == 1

    def test_writes_draft_and_audit(self, tmp_state, config):
        from lead_hub.process_lead import main
        lead = _make_lead("Please quote for an EICR.")
        append_lead("example-client", lead)

        main(["example-client", lead.lead_id, "--dry-run"])

        assert len(read_assistant_runs("example-client")) == 1
        assert len(read_audit_events("example-client")) == 1


# ---------------------------------------------------------------------------
# process_new_leads CLI
# ---------------------------------------------------------------------------


class TestProcessNewLeadsCLI:
    def test_processes_only_new_leads(self, tmp_state, config):
        from lead_hub.process_new_leads import main

        new_lead_1 = _make_lead("I need an EICR.", name="Alice")
        new_lead_2 = _make_lead("I need an EV charger.", service="ev-charger", name="Bob")
        already_processed = _make_lead("Already done.", name="Charlie")

        for l in [new_lead_1, new_lead_2, already_processed]:
            append_lead("example-client", l)

        # Mark Charlie as already replied
        from lead_hub.storage import update_lead_status
        update_lead_status("example-client", already_processed.lead_id, LeadStatus.replied)

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        leads = read_leads("example-client")
        statuses = {l.name: l.status for l in leads}
        assert statuses["Alice"] != LeadStatus.new
        assert statuses["Bob"] != LeadStatus.new
        assert statuses["Charlie"] == LeadStatus.replied  # untouched

    def test_no_new_leads_exits_zero(self, tmp_state):
        from lead_hub.process_new_leads import main
        rc = main(["example-client", "--dry-run"])
        assert rc == 0

    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.process_new_leads import main
        rc = main([])
        assert rc == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.process_new_leads import main
        rc = main(["no-such-client", "--dry-run"])
        assert rc == 1

    def test_bulk_writes_drafts_and_audit(self, tmp_state, config):
        from lead_hub.process_new_leads import main
        for i in range(3):
            append_lead("example-client", _make_lead(f"I need an EICR for property {i}.", name=f"Lead {i}"))

        main(["example-client", "--dry-run"])

        assert len(read_assistant_runs("example-client")) == 3
        assert len(read_audit_events("example-client")) == 3
