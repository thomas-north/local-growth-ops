"""
Tests for the normalized lead model and JSONL storage layer.

All test data is fictional. Tests use a temporary directory via
LOCAL_GROWTH_STATE_ROOT — they never write to /var/openclaw/.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lead_hub.schemas.lead import (
    ConsentInfo,
    ContactInfo,
    ContactMethod,
    LeadStatus,
    NormalizedLead,
    Urgency,
    new_lead,
)
from lead_hub.storage import (
    append_lead,
    leads_path,
    list_due_followups,
    read_leads,
    state_root,
    update_lead_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def tmp_state(tmp_path, monkeypatch):
    """Redirect all storage to a temp dir via LOCAL_GROWTH_STATE_ROOT."""
    monkeypatch.setenv("LOCAL_GROWTH_STATE_ROOT", str(tmp_path))
    return tmp_path


def _contact(**kwargs) -> ContactInfo:
    defaults = {"email": "lead@example.invalid", "phone": None}
    defaults.update(kwargs)
    return ContactInfo(**defaults)


def _consent(**kwargs) -> ConsentInfo:
    defaults = {"privacy_accepted": False, "marketing_opt_in": False}
    defaults.update(kwargs)
    return ConsentInfo(**defaults)


def _make_lead(**kwargs) -> NormalizedLead:
    defaults = dict(
        client_id="example-client",
        source="manual",
        name="Test Lead",
        contact=_contact(),
        message="Please quote for an EICR.",
        consent=_consent(),
    )
    defaults.update(kwargs)
    return new_lead(**defaults)


# ---------------------------------------------------------------------------
# Lead schema — valid creation
# ---------------------------------------------------------------------------


class TestLeadCreation:
    def test_new_lead_has_uuid(self):
        lead = _make_lead()
        assert len(lead.lead_id) == 36  # UUID4 format
        assert "-" in lead.lead_id

    def test_new_lead_status_is_new(self):
        lead = _make_lead()
        assert lead.status == LeadStatus.new

    def test_new_lead_received_at_is_utc_aware(self):
        lead = _make_lead()
        assert lead.received_at.tzinfo is not None

    def test_new_lead_defaults(self):
        lead = _make_lead()
        assert lead.urgency == Urgency.normal
        assert lead.next_followup_at is None
        assert lead.assigned_owner == ""
        assert lead.conversation_summary == ""

    def test_email_only_contact_valid(self):
        lead = _make_lead(contact=ContactInfo(email="a@b.invalid"))
        assert lead.contact.email == "a@b.invalid"

    def test_phone_only_contact_valid(self):
        lead = _make_lead(contact=ContactInfo(phone="07700000000"))
        assert lead.contact.phone == "07700000000"

    def test_manual_lead_privacy_false_accepted(self):
        """Manual test leads may have privacy_accepted=False."""
        lead = _make_lead(consent=ConsentInfo(privacy_accepted=False))
        assert lead.consent.privacy_accepted is False


# ---------------------------------------------------------------------------
# Lead schema — validation failures
# ---------------------------------------------------------------------------


class TestLeadValidation:
    def test_empty_name_fails(self):
        with pytest.raises(Exception):
            _make_lead(name="")

    def test_empty_message_fails(self):
        with pytest.raises(Exception):
            _make_lead(message="")

    def test_empty_source_fails(self):
        with pytest.raises(Exception):
            _make_lead(source="")

    def test_no_contact_details_fails(self):
        with pytest.raises(Exception):
            ContactInfo(email=None, phone=None)

    def test_blank_email_fails(self):
        with pytest.raises(Exception):
            ContactInfo(email="   ", phone=None)

    def test_invalid_urgency_fails(self):
        with pytest.raises(Exception):
            NormalizedLead(
                lead_id="abc-123",
                client_id="example-client",
                source="manual",
                name="Test",
                contact=_contact(),
                message="Hello",
                urgency="critical",  # type: ignore[arg-type]
                consent=_consent(),
                received_at=_NOW,
            )

    def test_naive_received_at_fails(self):
        with pytest.raises(Exception):
            NormalizedLead(
                lead_id="abc-123",
                client_id="example-client",
                source="manual",
                name="Test",
                contact=_contact(),
                message="Hello",
                consent=_consent(),
                received_at=datetime(2026, 6, 1, 12, 0, 0),  # no tzinfo
            )

    def test_naive_next_followup_fails(self):
        with pytest.raises(Exception):
            NormalizedLead(
                lead_id="abc-123",
                client_id="example-client",
                source="manual",
                name="Test",
                contact=_contact(),
                message="Hello",
                consent=_consent(),
                received_at=_NOW,
                next_followup_at=datetime(2026, 6, 4, 9, 0, 0),  # no tzinfo
            )

    def test_invalid_lead_id_slug_fails(self):
        with pytest.raises(Exception):
            NormalizedLead(
                lead_id="",
                client_id="example-client",
                source="manual",
                name="Test",
                contact=_contact(),
                message="Hello",
                consent=_consent(),
                received_at=_NOW,
            )


# ---------------------------------------------------------------------------
# JSONL storage round-trip
# ---------------------------------------------------------------------------


class TestStorage:
    def test_state_root_uses_env(self, tmp_state):
        assert state_root() == tmp_state

    def test_no_leads_returns_empty_list(self, tmp_state):
        assert read_leads("example-client") == []

    def test_append_and_read_single_lead(self, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        leads = read_leads("example-client")
        assert len(leads) == 1
        assert leads[0].lead_id == lead.lead_id
        assert leads[0].name == "Test Lead"

    def test_append_multiple_leads_preserves_order(self, tmp_state):
        lead_a = _make_lead(name="Alice")
        lead_b = _make_lead(name="Bob")
        append_lead("example-client", lead_a)
        append_lead("example-client", lead_b)
        leads = read_leads("example-client")
        assert len(leads) == 2
        assert leads[0].name == "Alice"
        assert leads[1].name == "Bob"

    def test_leads_are_isolated_per_client(self, tmp_state):
        lead_a = _make_lead(client_id="example-client")
        lead_b = _make_lead(client_id="other-client")
        append_lead("example-client", lead_a)
        append_lead("other-client", lead_b)
        assert len(read_leads("example-client")) == 1
        assert len(read_leads("other-client")) == 1

    def test_jsonl_round_trip_preserves_all_fields(self, tmp_state):
        followup = datetime(2026, 6, 4, 9, 0, 0, tzinfo=timezone.utc)
        original = _make_lead(
            name="Round Trip",
            contact=ContactInfo(email="rt@example.invalid", phone="07700000001"),
            message="Testing round-trip serialization.",
            service_requested="full-rewire",
            urgency=Urgency.high,
            consent=ConsentInfo(privacy_accepted=False, marketing_opt_in=False),
            next_followup_at=followup,
            assigned_owner="operator",
        )
        append_lead("example-client", original)
        loaded = read_leads("example-client")[0]

        assert loaded.lead_id == original.lead_id
        assert loaded.contact.email == "rt@example.invalid"
        assert loaded.contact.phone == "07700000001"
        assert loaded.service_requested == "full-rewire"
        assert loaded.urgency == Urgency.high
        assert loaded.next_followup_at == followup
        assert loaded.assigned_owner == "operator"


# ---------------------------------------------------------------------------
# Status updates
# ---------------------------------------------------------------------------


class TestStatusUpdate:
    def test_update_status(self, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        updated = update_lead_status(
            "example-client", lead.lead_id, LeadStatus.needs_reply_draft
        )
        assert updated.status == LeadStatus.needs_reply_draft
        # Persisted correctly
        persisted = read_leads("example-client")[0]
        assert persisted.status == LeadStatus.needs_reply_draft

    def test_update_status_with_followup(self, tmp_state):
        lead = _make_lead()
        append_lead("example-client", lead)
        followup = datetime(2026, 6, 10, 9, 0, 0, tzinfo=timezone.utc)
        updated = update_lead_status(
            "example-client",
            lead.lead_id,
            LeadStatus.followup_scheduled,
            next_followup_at=followup,
        )
        assert updated.status == LeadStatus.followup_scheduled
        assert updated.next_followup_at == followup

    def test_update_preserves_other_leads(self, tmp_state):
        lead_a = _make_lead(name="Alice")
        lead_b = _make_lead(name="Bob")
        append_lead("example-client", lead_a)
        append_lead("example-client", lead_b)
        update_lead_status("example-client", lead_a.lead_id, LeadStatus.spam)
        leads = read_leads("example-client")
        bob = next(l for l in leads if l.name == "Bob")
        assert bob.status == LeadStatus.new

    def test_update_unknown_lead_raises_key_error(self, tmp_state):
        with pytest.raises(KeyError, match="no-such-id"):
            update_lead_status("example-client", "no-such-id", LeadStatus.closed)


# ---------------------------------------------------------------------------
# Due follow-up filtering
# ---------------------------------------------------------------------------


class TestDueFollowups:
    def _make_with_followup(self, dt: datetime) -> NormalizedLead:
        return _make_lead(next_followup_at=dt)

    def test_no_followups_returns_empty(self, tmp_state):
        append_lead("example-client", _make_lead())
        assert list_due_followups("example-client", as_of=_NOW) == []

    def test_past_followup_returned(self, tmp_state):
        past = _NOW - timedelta(hours=1)
        lead = self._make_with_followup(past)
        append_lead("example-client", lead)
        due = list_due_followups("example-client", as_of=_NOW)
        assert len(due) == 1
        assert due[0].lead_id == lead.lead_id

    def test_exact_now_followup_returned(self, tmp_state):
        lead = self._make_with_followup(_NOW)
        append_lead("example-client", lead)
        due = list_due_followups("example-client", as_of=_NOW)
        assert len(due) == 1

    def test_future_followup_not_returned(self, tmp_state):
        future = _NOW + timedelta(hours=1)
        lead = self._make_with_followup(future)
        append_lead("example-client", lead)
        due = list_due_followups("example-client", as_of=_NOW)
        assert due == []

    def test_mixed_followups_only_due_returned(self, tmp_state):
        past = _NOW - timedelta(days=1)
        future = _NOW + timedelta(days=1)
        lead_past = self._make_with_followup(past)
        lead_future = self._make_with_followup(future)
        lead_none = _make_lead()
        for l in [lead_past, lead_future, lead_none]:
            append_lead("example-client", l)
        due = list_due_followups("example-client", as_of=_NOW)
        assert len(due) == 1
        assert due[0].lead_id == lead_past.lead_id


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestManualLeadCLI:
    def test_creates_lead_with_email(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main([
            "example-client",
            "--name", "Test Lead",
            "--email", "lead@example.invalid",
            "--message", "Please quote for an EICR",
        ])
        assert rc == 0
        leads = read_leads("example-client")
        assert len(leads) == 1
        assert leads[0].name == "Test Lead"
        assert leads[0].source == "manual"

    def test_creates_lead_with_phone(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main(["example-client", "--phone", "07700000000", "--message", "Call me"])
        assert rc == 0

    def test_no_contact_exits_two(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main(["example-client", "--message", "No contact provided"])
        assert rc == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main(["no-such-client", "--email", "x@x.invalid", "--message", "Hi"])
        assert rc == 1


class TestListLeadsCLI:
    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.list_leads import main
        assert main([]) == 2

    def test_empty_list_exits_zero(self, tmp_state):
        from lead_hub.list_leads import main
        assert main(["example-client"]) == 0

    def test_shows_created_lead(self, tmp_state):
        from lead_hub.manual_lead import main as create
        from lead_hub.list_leads import main as list_cmd
        create(["example-client", "--email", "a@example.invalid", "--message", "Hi"])
        assert list_cmd(["example-client"]) == 0

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.list_leads import main
        assert main(["no-such-client"]) == 1


class TestListDueFollowupsCLI:
    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.list_due_followups import main
        assert main([]) == 2

    def test_no_due_exits_zero(self, tmp_state):
        from lead_hub.list_due_followups import main
        assert main(["example-client"]) == 0

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.list_due_followups import main
        assert main(["no-such-client"]) == 1
