"""
Tests for the intake adapter schemas and ingestion command.

All test data is fictional. Tests use tmp_state (monkeypatched
LOCAL_GROWTH_STATE_ROOT) and never write to /var/openclaw/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lead_hub.schemas.intake import (
    ManualLeadPayload,
    WebsiteLeadPayload,
    manual_payload_to_lead,
    website_payload_to_lead,
)
from lead_hub.schemas.lead import ContactMethod, LeadStatus, Urgency
from lead_hub.storage import read_leads

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SUBMITTED_AT = datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc)

_VALID_WEBSITE: dict = {
    "client_id": "example-client",
    "site_id": "example-client-main",
    "source_page": "/contact",
    "submitted_at": "2026-06-01T10:30:00+00:00",
    "name": "Jane Smith",
    "preferred_contact_method": "email",
    "email": "jane@example.invalid",
    "phone": None,
    "service_requested": "eicr",
    "urgency": "normal",
    "message": "I need a landlord electrical certificate.",
    "privacy_accepted": True,
    "marketing_opt_in": False,
}


@pytest.fixture()
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_GROWTH_STATE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture()
def valid_payload_file(tmp_path) -> Path:
    """Write the valid website payload fixture to a temp file."""
    p = tmp_path / "payload.json"
    p.write_text(json.dumps(_VALID_WEBSITE), encoding="utf-8")
    return p


def _website(**overrides) -> dict:
    import copy
    d = copy.deepcopy(_VALID_WEBSITE)
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# WebsiteLeadPayload — happy path
# ---------------------------------------------------------------------------


class TestWebsitePayloadValid:
    def test_valid_payload_parses(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        assert p.name == "Jane Smith"
        assert p.privacy_accepted is True
        assert p.urgency == Urgency.normal

    def test_email_only_accepted(self):
        p = WebsiteLeadPayload.model_validate(_website(phone=None))
        assert p.email == "jane@example.invalid"

    def test_phone_only_accepted(self):
        d = _website(email=None, phone="07700000000",
                     preferred_contact_method="phone")
        p = WebsiteLeadPayload.model_validate(d)
        assert p.phone == "07700000000"

    def test_both_contact_methods_accepted(self):
        d = _website(phone="07700000001")
        p = WebsiteLeadPayload.model_validate(d)
        assert p.email and p.phone

    def test_marketing_opt_in_defaults_false(self):
        d = _website()
        del d["marketing_opt_in"]
        p = WebsiteLeadPayload.model_validate(d)
        assert p.marketing_opt_in is False

    def test_fixture_file_parses(self):
        fixture = Path(__file__).parent / "fixtures" / "website_payload_valid.json"
        data = json.loads(fixture.read_text())
        p = WebsiteLeadPayload.model_validate(data)
        assert p.client_id == "example-client"


# ---------------------------------------------------------------------------
# WebsiteLeadPayload — validation failures
# ---------------------------------------------------------------------------


class TestWebsitePayloadInvalid:
    def test_privacy_not_accepted_fails(self):
        with pytest.raises(Exception, match="privacy_accepted"):
            WebsiteLeadPayload.model_validate(_website(privacy_accepted=False))

    def test_no_contact_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(
                _website(email=None, phone=None)
            )

    def test_blank_email_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(_website(email="   "))

    def test_empty_name_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(_website(name=""))

    def test_empty_message_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(_website(message=""))

    def test_empty_client_id_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(_website(client_id=""))

    def test_naive_submitted_at_fails(self):
        with pytest.raises(Exception):
            WebsiteLeadPayload.model_validate(
                _website(submitted_at="2026-06-01T10:30:00")  # no tz
            )


# ---------------------------------------------------------------------------
# website_payload_to_lead conversion
# ---------------------------------------------------------------------------


class TestWebsitePayloadConversion:
    def test_source_is_website_site_id(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.source == "website:example-client-main"

    def test_received_at_comes_from_submitted_at(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.received_at == _SUBMITTED_AT

    def test_status_is_new(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.status == LeadStatus.new

    def test_next_followup_is_null(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.next_followup_at is None

    def test_privacy_accepted_true_on_stored_lead(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.consent.privacy_accepted is True

    def test_contact_email_preserved(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.contact.email == "jane@example.invalid"

    def test_preferred_contact_method_preserved(self):
        p = WebsiteLeadPayload.model_validate(_VALID_WEBSITE)
        lead = website_payload_to_lead(p)
        assert lead.contact.preferred_method == ContactMethod.email


# ---------------------------------------------------------------------------
# ManualLeadPayload — happy path and failures
# ---------------------------------------------------------------------------


class TestManualPayload:
    def _make(self, **kwargs) -> ManualLeadPayload:
        defaults = dict(
            client_id="example-client",
            name="Test Lead",
            email="test@example.invalid",
            message="Manual test.",
        )
        defaults.update(kwargs)
        return ManualLeadPayload(**defaults)

    def test_valid_manual_payload(self):
        p = self._make()
        assert p.name == "Test Lead"

    def test_no_contact_fails(self):
        with pytest.raises(Exception):
            ManualLeadPayload(
                client_id="example-client",
                name="Test",
                message="Hi",
            )

    def test_empty_name_fails(self):
        with pytest.raises(Exception):
            self._make(name="")

    def test_source_is_manual_on_converted_lead(self):
        p = self._make()
        lead = manual_payload_to_lead(p)
        assert lead.source == "manual"

    def test_privacy_accepted_false_on_manual_lead(self):
        p = self._make()
        lead = manual_payload_to_lead(p)
        assert lead.consent.privacy_accepted is False


# ---------------------------------------------------------------------------
# ingest_website_payload CLI
# ---------------------------------------------------------------------------


class TestIngestWebsitePayloadCLI:
    def test_valid_payload_ingested(self, tmp_state, valid_payload_file):
        from lead_hub.ingest_website_payload import main
        rc = main(["example-client", str(valid_payload_file)])
        assert rc == 0
        leads = read_leads("example-client")
        assert len(leads) == 1
        assert leads[0].source == "website:example-client-main"
        assert leads[0].consent.privacy_accepted is True

    def test_missing_args_exits_two(self, tmp_state):
        from lead_hub.ingest_website_payload import main
        assert main([]) == 2
        assert main(["example-client"]) == 2

    def test_missing_payload_file_exits_one(self, tmp_state):
        from lead_hub.ingest_website_payload import main
        assert main(["example-client", "/tmp/no-such-file.json"]) == 1

    def test_missing_client_exits_one(self, tmp_state, valid_payload_file):
        from lead_hub.ingest_website_payload import main
        assert main(["no-such-client", str(valid_payload_file)]) == 1

    def test_privacy_false_exits_one(self, tmp_state, tmp_path):
        from lead_hub.ingest_website_payload import main
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps(_website(privacy_accepted=False)))
        assert main(["example-client", str(bad)]) == 1

    def test_client_id_mismatch_exits_one(self, tmp_state, tmp_path):
        from lead_hub.ingest_website_payload import main
        mismatched = tmp_path / "mismatch.json"
        mismatched.write_text(json.dumps(_website(client_id="other-client")))
        assert main(["example-client", str(mismatched)]) == 1

    def test_no_contact_exits_one(self, tmp_state, tmp_path):
        from lead_hub.ingest_website_payload import main
        no_contact = tmp_path / "nocontact.json"
        no_contact.write_text(
            json.dumps(_website(email=None, phone=None))
        )
        assert main(["example-client", str(no_contact)]) == 1

    def test_list_leads_shows_ingested_lead(self, tmp_state, valid_payload_file):
        from lead_hub.ingest_website_payload import main as ingest
        from lead_hub.list_leads import main as list_cmd
        ingest(["example-client", str(valid_payload_file)])
        assert list_cmd(["example-client"]) == 0


# ---------------------------------------------------------------------------
# manual_lead CLI backward compatibility
# ---------------------------------------------------------------------------


class TestManualLeadCLIBackwardCompat:
    def test_manual_lead_still_works(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main([
            "example-client",
            "--name", "Manual Lead",
            "--email", "manual@example.invalid",
            "--message", "Manual test",
        ])
        assert rc == 0
        leads = read_leads("example-client")
        assert len(leads) == 1
        assert leads[0].source == "manual"
        assert leads[0].name == "Manual Lead"

    def test_manual_lead_no_contact_still_exits_two(self, tmp_state):
        from lead_hub.manual_lead import main
        assert main(["example-client", "--message", "No contact"]) == 2

    def test_manual_lead_all_flags_work(self, tmp_state):
        from lead_hub.manual_lead import main
        rc = main([
            "example-client",
            "--name", "Full Test",
            "--email", "full@example.invalid",
            "--phone", "07700000002",
            "--service", "ev-charger",
            "--message", "Full flags test.",
            "--urgency", "high",
        ])
        assert rc == 0
        leads = read_leads("example-client")
        assert leads[0].urgency == Urgency.high

    # --- Regression: preferred_contact_method must be inferred from flags ---
    # Before the plan-0004 refactor this was set explicitly in the CLI.
    # The refactor accidentally dropped it, leaving every manual lead as
    # preferred_method=unknown. These tests pin the correct behaviour.

    def test_email_only_sets_preferred_email(self, tmp_state):
        from lead_hub.manual_lead import main
        main([
            "example-client",
            "--email", "e@example.invalid",
            "--message", "Email-only lead",
        ])
        leads = read_leads("example-client")
        assert leads[0].contact.preferred_method == ContactMethod.email

    def test_phone_only_sets_preferred_phone(self, tmp_state):
        from lead_hub.manual_lead import main
        main([
            "example-client",
            "--phone", "07700000099",
            "--message", "Phone-only lead",
        ])
        leads = read_leads("example-client")
        assert leads[0].contact.preferred_method == ContactMethod.phone

    def test_both_contact_methods_prefers_email(self, tmp_state):
        """When both --email and --phone are given, email takes precedence."""
        from lead_hub.manual_lead import main
        main([
            "example-client",
            "--email", "both@example.invalid",
            "--phone", "07700000098",
            "--message", "Both-contact lead",
        ])
        leads = read_leads("example-client")
        assert leads[0].contact.preferred_method == ContactMethod.email
