"""
tests/test_followup.py
~~~~~~~~~~~~~~~~~~~~~~
Tests for the follow-up scheduler and weekly report.

All data is fictional. Tests use LOCAL_GROWTH_STATE_ROOT via monkeypatch.
No network calls or real Telegram sends are made.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lead_hub.followup_scheduler import (
    EXCLUDED_STATUSES,
    build_followup_draft,
    compute_next_followup_at,
    count_followup_drafts,
    make_followup_audit_event,
    run_followup_workflow,
)
from lead_hub.schemas.assistant_workflow import AuditEventKind
from lead_hub.schemas.client_config import ClientAssistantConfig
from lead_hub.schemas.lead import (
    ConsentInfo,
    ContactInfo,
    LeadStatus,
    NormalizedLead,
    Urgency,
    new_lead,
)
from lead_hub.storage import (
    append_audit_event,
    append_lead,
    read_audit_events,
    read_assistant_runs,
    update_lead_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
_PAST = _NOW - timedelta(days=5)

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
    "hours": {"monday_friday": "08:00-18:00", "saturday": "09:00-13:00", "sunday": "Closed"},
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
    name: str = "Jane Smith",
    service: str = "eicr",
    status: LeadStatus = LeadStatus.replied,
    next_followup_at: datetime | None = None,
) -> NormalizedLead:
    lead = new_lead(
        client_id="example-client",
        source="manual",
        name=name,
        contact=ContactInfo(email="jane@example.invalid"),
        message=message,
        service_requested=service,
        urgency=Urgency.normal,
        consent=ConsentInfo(privacy_accepted=False),
        next_followup_at=next_followup_at,
    )
    # Override status for test setup (new_lead always returns LeadStatus.new)
    return lead.model_copy(update={"status": status})


# ---------------------------------------------------------------------------
# EXCLUDED_STATUSES
# ---------------------------------------------------------------------------


class TestExcludedStatuses:
    def test_spam_excluded(self):
        assert LeadStatus.spam in EXCLUDED_STATUSES

    def test_escalated_excluded(self):
        assert LeadStatus.escalated in EXCLUDED_STATUSES

    def test_closed_excluded(self):
        assert LeadStatus.closed in EXCLUDED_STATUSES

    def test_won_excluded(self):
        assert LeadStatus.won in EXCLUDED_STATUSES

    def test_lost_excluded(self):
        assert LeadStatus.lost in EXCLUDED_STATUSES

    def test_replied_not_excluded(self):
        assert LeadStatus.replied not in EXCLUDED_STATUSES

    def test_followup_scheduled_not_excluded(self):
        assert LeadStatus.followup_scheduled not in EXCLUDED_STATUSES


# ---------------------------------------------------------------------------
# compute_next_followup_at
# ---------------------------------------------------------------------------


class TestComputeNextFollowupAt:
    def test_followup_0_returns_first_followup_days(self, config):
        result = compute_next_followup_at(config, _PAST, followup_number=0)
        expected = _PAST + timedelta(days=config.followup.first_followup_days)
        assert result == expected

    def test_followup_1_returns_second_followup_days(self, config):
        result = compute_next_followup_at(config, _PAST, followup_number=1)
        expected = _PAST + timedelta(days=config.followup.second_followup_days)
        assert result == expected

    def test_at_max_returns_none(self, config):
        result = compute_next_followup_at(
            config, _PAST, followup_number=config.followup.max_followups
        )
        assert result is None

    def test_beyond_max_returns_none(self, config):
        result = compute_next_followup_at(config, _PAST, followup_number=99)
        assert result is None


# ---------------------------------------------------------------------------
# count_followup_drafts
# ---------------------------------------------------------------------------


class TestCountFollowupDrafts:
    def test_returns_zero_with_no_events(self, tmp_state, config):
        lead = _make_lead()
        append_lead("example-client", lead)
        assert count_followup_drafts("example-client", lead.lead_id) == 0

    def test_counts_followup_draft_created_events(self, tmp_state, config):
        lead = _make_lead()
        append_lead("example-client", lead)
        run = run_followup_workflow(lead, config, 0)
        event = make_followup_audit_event(lead, run, lead.status, 0)
        append_audit_event("example-client", event)
        assert count_followup_drafts("example-client", lead.lead_id) == 1

    def test_does_not_count_other_event_kinds(self, tmp_state, config):
        from lead_hub.schemas.assistant_workflow import AuditEvent
        import uuid
        lead = _make_lead()
        append_lead("example-client", lead)
        # Add a non-followup audit event
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            lead_id=lead.lead_id,
            client_id="example-client",
            kind=AuditEventKind.processed,
            occurred_at=_NOW,
            detail="processed",
            previous_status=lead.status,
            new_status=lead.status,
        )
        append_audit_event("example-client", event)
        assert count_followup_drafts("example-client", lead.lead_id) == 0


# ---------------------------------------------------------------------------
# build_followup_draft
# ---------------------------------------------------------------------------


class TestBuildFollowupDraft:
    def test_approval_required_always_true(self, config):
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        assert draft.approval_required is True

    def test_sign_off_in_draft(self, config):
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        assert "Tom, Bright Spark Electrical" in draft.draft_body

    def test_no_invented_price_in_draft(self, config):
        from lead_hub.assistant import _contains_invented_price
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        assert not _contains_invented_price(draft.draft_body)

    def test_no_availability_promise_in_draft(self, config):
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        body_lower = draft.draft_body.lower()
        for phrase in ["available tomorrow", "available on", "we can come"]:
            assert phrase not in body_lower

    def test_first_followup_subject_differs_from_second(self, config):
        lead = _make_lead()
        draft1 = build_followup_draft(lead, config, followup_number=0)
        draft2 = build_followup_draft(lead, config, followup_number=1)
        assert draft1.draft_subject != draft2.draft_subject

    def test_operator_notes_include_followup_number(self, config):
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        assert "1" in draft.operator_notes

    def test_assumptions_list_populated(self, config):
        lead = _make_lead()
        draft = build_followup_draft(lead, config, followup_number=0)
        assert len(draft.assumptions) > 0


# ---------------------------------------------------------------------------
# run_followup_workflow
# ---------------------------------------------------------------------------


class TestRunFollowupWorkflow:
    def test_uses_followup_adapter(self, config):
        lead = _make_lead()
        run = run_followup_workflow(lead, config, followup_count=0)
        assert run.adapter == "followup-dry-run-v1"

    def test_genuine_lead_produces_draft(self, config):
        lead = _make_lead()
        run = run_followup_workflow(lead, config, followup_count=0)
        assert run.draft_reply is not None
        assert run.new_status == LeadStatus.followup_scheduled

    def test_escalation_in_message_produces_no_draft(self, config):
        lead = _make_lead(message="I want to complain and speak to a solicitor.")
        run = run_followup_workflow(lead, config, followup_count=0)
        assert run.draft_reply is None
        assert run.new_status == LeadStatus.escalated

    def test_approval_required_in_draft(self, config):
        lead = _make_lead()
        run = run_followup_workflow(lead, config, followup_count=0)
        assert run.draft_reply is not None
        assert run.draft_reply.approval_required is True


# ---------------------------------------------------------------------------
# process_due_followups CLI
# ---------------------------------------------------------------------------


class TestProcessDueFollowupsCLI:
    def _add_due_lead(
        self,
        client_slug: str = "example-client",
        name: str = "Jane Smith",
        status: LeadStatus = LeadStatus.replied,
    ) -> NormalizedLead:
        lead = new_lead(
            client_id=client_slug,
            source="manual",
            name=name,
            contact=ContactInfo(email="jane@example.invalid"),
            message="Please quote for an EICR.",
            service_requested="eicr",
            urgency=Urgency.normal,
            consent=ConsentInfo(privacy_accepted=False),
            next_followup_at=_PAST,  # in the past -> due now
        )
        lead = lead.model_copy(update={"status": status})
        append_lead(client_slug, lead)
        return lead

    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.process_due_followups import main
        assert main([]) == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.process_due_followups import main
        assert main(["no-such-client", "--dry-run"]) == 1

    def test_no_due_leads_exits_zero(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        assert main(["example-client", "--dry-run"]) == 0

    def test_processes_due_replied_lead(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        self._add_due_lead()
        rc = main(["example-client", "--dry-run"])
        assert rc == 0
        runs = read_assistant_runs("example-client")
        assert len(runs) == 1
        assert runs[0].adapter == "followup-dry-run-v1"

    def test_updates_status_to_followup_scheduled(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        from lead_hub.storage import read_leads
        self._add_due_lead()
        main(["example-client", "--dry-run"])
        leads = read_leads("example-client")
        assert leads[0].status == LeadStatus.followup_scheduled

    def test_writes_followup_draft_created_audit_event(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        self._add_due_lead()
        main(["example-client", "--dry-run"])
        events = read_audit_events("example-client")
        kinds = [e.kind for e in events]
        assert AuditEventKind.followup_draft_created in kinds

    def test_skips_excluded_status(self, tmp_state, config, capsys):
        from lead_hub.process_due_followups import main
        self._add_due_lead(status=LeadStatus.spam)
        rc = main(["example-client", "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "SKIP" in captured.err
        runs = read_assistant_runs("example-client")
        assert len(runs) == 0

    def test_skips_when_max_followups_exhausted(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        lead = self._add_due_lead()
        # Pre-populate audit with max_followups events
        for i in range(config.followup.max_followups):
            run = run_followup_workflow(lead, config, i)
            event = make_followup_audit_event(lead, run, lead.status, i)
            append_audit_event("example-client", event)

        rc = main(["example-client", "--dry-run"])
        assert rc == 0
        # No new runs should be added
        runs = read_assistant_runs("example-client")
        assert len(runs) == 0

    def test_next_followup_at_set_after_first(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        from lead_hub.storage import read_leads
        self._add_due_lead()
        main(["example-client", "--dry-run"])
        leads = read_leads("example-client")
        # After first follow-up, next_followup_at should be set
        assert leads[0].next_followup_at is not None

    def test_next_followup_at_cleared_after_last(self, tmp_state, config):
        from lead_hub.process_due_followups import main
        from lead_hub.storage import read_leads
        lead = self._add_due_lead()
        # Pre-populate one audit event so this is the last allowed followup
        run0 = run_followup_workflow(lead, config, 0)
        event0 = make_followup_audit_event(lead, run0, lead.status, 0)
        append_audit_event("example-client", event0)
        # max_followups=2, so after this second one, next_followup_at should be None
        main(["example-client", "--dry-run"])
        leads = read_leads("example-client")
        assert leads[0].next_followup_at is None


# ---------------------------------------------------------------------------
# weekly_report CLI
# ---------------------------------------------------------------------------


class TestWeeklyReportCLI:
    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.weekly_report import main
        assert main([]) == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.weekly_report import main
        assert main(["no-such-client"]) == 1

    def test_empty_state_exits_zero(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        rc = main(["example-client"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bright Spark Electrical" in out
        assert "WEEKLY OPS REPORT" in out

    def test_counts_match_actual_leads(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        for i in range(3):
            lead = new_lead(
                client_id="example-client",
                source="manual",
                name=f"Lead {i}",
                contact=ContactInfo(email=f"lead{i}@example.invalid"),
                message="EICR enquiry",
                service_requested="eicr",
                urgency=Urgency.normal,
                consent=ConsentInfo(privacy_accepted=False),
                next_followup_at=None,
            )
            append_lead("example-client", lead)

        main(["example-client"])
        out = capsys.readouterr().out
        assert "Total leads on record: 3" in out

    def test_pending_approvals_section_shows_names(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        lead = new_lead(
            client_id="example-client",
            source="manual",
            name="Alice Pending",
            contact=ContactInfo(email="alice@example.invalid"),
            message="EICR please",
            service_requested="eicr",
            urgency=Urgency.normal,
            consent=ConsentInfo(privacy_accepted=False),
            next_followup_at=None,
        )
        append_lead("example-client", lead)
        update_lead_status("example-client", lead.lead_id, LeadStatus.awaiting_approval)
        main(["example-client"])
        out = capsys.readouterr().out
        assert "Alice Pending" in out
        assert "PENDING APPROVALS" in out

    def test_report_does_not_contain_email(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        lead = new_lead(
            client_id="example-client",
            source="manual",
            name="PII Test",
            contact=ContactInfo(email="secret-pii@example.invalid"),
            message="EICR please",
            service_requested="eicr",
            urgency=Urgency.normal,
            consent=ConsentInfo(privacy_accepted=False),
            next_followup_at=None,
        )
        append_lead("example-client", lead)
        main(["example-client"])
        out = capsys.readouterr().out
        assert "secret-pii@example.invalid" not in out

    def test_recommended_actions_present(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        main(["example-client"])
        out = capsys.readouterr().out
        assert "RECOMMENDED OPERATOR ACTIONS" in out

    def test_due_followups_section(self, tmp_state, config, capsys):
        from lead_hub.weekly_report import main
        lead = new_lead(
            client_id="example-client",
            source="manual",
            name="Bob Overdue",
            contact=ContactInfo(email="bob@example.invalid"),
            message="EV charger please",
            service_requested="ev-charger",
            urgency=Urgency.normal,
            consent=ConsentInfo(privacy_accepted=False),
            next_followup_at=_PAST,
        )
        append_lead("example-client", lead)
        update_lead_status(
            "example-client", lead.lead_id,
            LeadStatus.followup_scheduled,
            next_followup_at=_PAST,
        )
        main(["example-client"])
        out = capsys.readouterr().out
        assert "Bob Overdue" in out
        assert "FOLLOW-UPS DUE" in out
