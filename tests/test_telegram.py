"""
tests/test_telegram.py
~~~~~~~~~~~~~~~~~~~~~~
Tests for the Telegram operator approval notification workflow.

All data is fictional. No real Telegram API calls are made — send_telegram_message
is always patched. Tests use LOCAL_GROWTH_STATE_ROOT via monkeypatch.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_hub.schemas.assistant_workflow import (
    AuditEventKind,
    Classification,
    Confidence,
    DraftReply,
    EscalationCheck,
    EscalationSeverity,
    LeadClassification,
    AssistantRun,
)
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
    append_assistant_run,
    append_lead,
    read_audit_events,
    update_lead_status,
)
from lead_hub.telegram_approval import (
    TelegramSendError,
    format_approval_message,
    redact_contact_details,
    resolve_bot_token,
    resolve_chat_id,
)

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

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

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def config() -> ClientAssistantConfig:
    return ClientAssistantConfig.model_validate(_CONFIG_DATA)


@pytest.fixture()
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_GROWTH_STATE_ROOT", str(tmp_path))
    return tmp_path


def _make_lead(
    message: str = "Please quote for an EICR for my rental property.",
    name: str = "Jane Smith",
    email: str = "jane@example.invalid",
    phone: str | None = None,
    service: str = "eicr",
) -> NormalizedLead:
    contact = ContactInfo(email=email, phone=phone)
    return new_lead(
        client_id="example-client",
        source="manual",
        name=name,
        contact=contact,
        message=message,
        service_requested=service,
        urgency=Urgency.normal,
        consent=ConsentInfo(privacy_accepted=False),
        next_followup_at=None,
    )


def _make_run(lead: NormalizedLead, with_draft: bool = True) -> AssistantRun:
    draft = None
    if with_draft:
        draft = DraftReply(
            draft_subject="Re: Your enquiry — Bright Spark Electrical",
            draft_body=(
                "Hi Jane,\n\n"
                "Thank you for getting in touch. We'd be happy to help with your EICR enquiry.\n\n"
                "Tom, Bright Spark Electrical"
            ),
            assumptions=["Service interpreted as: EICR", "Property assumed domestic/residential"],
            questions_for_lead=["How many circuits does the property have?"],
            operator_notes="Dry-run draft. Review tone before sending.",
            approval_required=True,
        )

    esc = EscalationCheck(
        escalation_required=False,
        severity=EscalationSeverity.none,
        reasons=[],
        operator_summary="",
        suggested_operator_action="",
    )
    cls = LeadClassification(
        classification=Classification.genuine_lead,
        confidence=Confidence.medium,
        summary="In-scope enquiry for eicr. Ready for reply draft.",
        recommended_next_status=LeadStatus.awaiting_approval,
        risk_flags=[],
        escalation_required=False,
        escalation_reason="",
    )
    import uuid
    return AssistantRun(
        run_id=str(uuid.uuid4()),
        lead_id=lead.lead_id,
        client_id="example-client",
        processed_at=_NOW,
        adapter="dry-run-v1",
        escalation_check=esc,
        classification=cls,
        draft_reply=draft,
        new_status=LeadStatus.awaiting_approval,
    )


# ---------------------------------------------------------------------------
# format_approval_message — content requirements
# ---------------------------------------------------------------------------


class TestFormatApprovalMessage:
    def test_includes_lead_name(self, config):
        lead = _make_lead(name="Alice Brown")
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "Alice Brown" in msg

    def test_includes_classification(self, config):
        lead = _make_lead()
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "genuine_lead" in msg

    def test_includes_draft_subject(self, config):
        lead = _make_lead()
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "Re: Your enquiry" in msg

    def test_includes_draft_body(self, config):
        lead = _make_lead()
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "Tom, Bright Spark Electrical" in msg

    def test_includes_approval_required_phrase(self, config):
        lead = _make_lead()
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "approval required" in msg.lower()

    def test_includes_operator_notes(self, config):
        lead = _make_lead()
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "Dry-run draft" in msg

    def test_does_not_include_lead_email(self, config):
        lead = _make_lead(email="secret@example.invalid")
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "secret@example.invalid" not in msg

    def test_does_not_include_lead_phone(self, config):
        lead = _make_lead(phone="07700900000", email="jane@example.invalid")
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "07700900000" not in msg

    def test_redacts_email_from_message_excerpt(self, config):
        lead = _make_lead(message="Please email me at private@example.invalid about the EICR.")
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "private@example.invalid" not in msg
        assert "[email redacted]" in msg

    def test_redacts_phone_from_message_excerpt(self, config):
        lead = _make_lead(message="Please call me on 07700 900123 about the EICR.")
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        assert "07700 900123" not in msg
        assert "[phone redacted]" in msg

    def test_long_message_is_excerpted(self, config):
        long_message = "A" * 500
        lead = _make_lead(message=long_message)
        run = _make_run(lead)
        msg = format_approval_message(lead, run, config)
        # Message excerpt is capped at 300 chars + ellipsis
        assert "A" * 400 not in msg

    def test_raises_if_no_draft(self, config):
        lead = _make_lead()
        run = _make_run(lead, with_draft=False)
        with pytest.raises(ValueError, match="no draft reply"):
            format_approval_message(lead, run, config)


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


class TestCredentialResolution:
    def test_bot_token_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        assert resolve_bot_token() == "test-token-123"

    def test_bot_token_absent_returns_none(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        assert resolve_bot_token() is None

    def test_chat_id_from_env_overrides_config(self, monkeypatch, config):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100987654321")
        assert resolve_chat_id(config) == "-100987654321"

    def test_chat_id_from_config_when_env_absent(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        config_data = {**_CONFIG_DATA}
        config_data = dict(_CONFIG_DATA)
        config_with_chat_id = ClientAssistantConfig.model_validate({
            **_CONFIG_DATA,
            "approval": {"telegram_chat_id": "-100111222333", "email": ""},
        })
        assert resolve_chat_id(config_with_chat_id) == "-100111222333"

    def test_chat_id_none_when_neither_set(self, monkeypatch, config):
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        # config has empty telegram_chat_id
        assert resolve_chat_id(config) is None


# ---------------------------------------------------------------------------
# PII redaction helper
# ---------------------------------------------------------------------------


class TestRedactContactDetails:
    def test_redacts_email_address(self):
        assert redact_contact_details("Email x@example.invalid please") == (
            "Email [email redacted] please"
        )

    def test_redacts_phone_number(self):
        assert redact_contact_details("Call 07700 900123 today") == (
            "Call [phone redacted] today"
        )


# ---------------------------------------------------------------------------
# AuditEventKind — notification_sent variant
# ---------------------------------------------------------------------------


class TestAuditEventKindExtended:
    def test_notification_sent_kind_exists(self):
        assert AuditEventKind.notification_sent.value == "notification_sent"


# ---------------------------------------------------------------------------
# notify_approvals CLI
# ---------------------------------------------------------------------------


class TestNotifyApprovalsCLI:
    def _setup_lead_with_run(self, client_slug: str) -> tuple:
        lead = _make_lead()
        append_lead(client_slug, lead)
        run = _make_run(lead)
        append_assistant_run(client_slug, run)
        update_lead_status(client_slug, lead.lead_id, LeadStatus.awaiting_approval)
        return lead, run

    def test_no_args_exits_two(self, tmp_state):
        from lead_hub.notify_approvals import main
        assert main([]) == 2

    def test_missing_client_exits_one(self, tmp_state):
        from lead_hub.notify_approvals import main
        assert main(["no-such-client", "--dry-run"]) == 1

    def test_zero_pending_exits_zero(self, tmp_state, config):
        from lead_hub.notify_approvals import main
        # No leads at all
        assert main(["example-client", "--dry-run"]) == 0

    def test_dry_run_prints_message(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main
        self._setup_lead_with_run("example-client")

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        captured = capsys.readouterr()
        assert "approval required" in captured.out.lower()
        assert "Jane Smith" in captured.out

    def test_dry_run_writes_audit_event(self, tmp_state, config):
        from lead_hub.notify_approvals import main
        self._setup_lead_with_run("example-client")

        main(["example-client", "--dry-run"])

        events = read_audit_events("example-client")
        kinds = [e.kind for e in events]
        assert AuditEventKind.notification_sent in kinds

    def test_dry_run_does_not_call_send(self, tmp_state, config, monkeypatch):
        from lead_hub.notify_approvals import main
        self._setup_lead_with_run("example-client")

        calls = []

        def fake_send(text, chat_id, bot_token):
            calls.append((text, chat_id, bot_token))

        monkeypatch.setattr("lead_hub.notify_approvals.send_telegram_message", fake_send)

        main(["example-client", "--dry-run"])
        assert calls == [], "send_telegram_message must not be called in dry-run mode"

    def test_live_mode_missing_token_exits_one(self, tmp_state, config, monkeypatch):
        from lead_hub.notify_approvals import main
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        self._setup_lead_with_run("example-client")
        assert main(["example-client"]) == 1

    def test_live_mode_missing_chat_id_exits_one(self, tmp_state, config, monkeypatch):
        from lead_hub.notify_approvals import main
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy-token")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        # config has empty telegram_chat_id → no chat ID
        self._setup_lead_with_run("example-client")
        assert main(["example-client"]) == 1

    def test_live_mode_calls_send(self, tmp_state, config, monkeypatch):
        from lead_hub.notify_approvals import main
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123456789")

        calls = []

        def fake_send(text, chat_id, bot_token):
            calls.append((text, chat_id, bot_token))

        monkeypatch.setattr("lead_hub.notify_approvals.send_telegram_message", fake_send)

        self._setup_lead_with_run("example-client")
        rc = main(["example-client"])

        assert rc == 0
        assert len(calls) == 1
        text, chat_id, token = calls[0]
        assert "approval required" in text.lower()
        assert chat_id == "-100123456789"
        assert token == "dummy-token"

    def test_live_send_error_exits_one(self, tmp_state, config, monkeypatch):
        from lead_hub.notify_approvals import main
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123456789")

        def failing_send(text, chat_id, bot_token):
            raise TelegramSendError("connection refused")

        monkeypatch.setattr("lead_hub.notify_approvals.send_telegram_message", failing_send)

        self._setup_lead_with_run("example-client")
        assert main(["example-client"]) == 1

    def test_skips_non_awaiting_approval_leads(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main

        # Create two leads: one awaiting approval, one already replied
        lead_pending = _make_lead(name="Pending Lead")
        lead_replied = _make_lead(name="Replied Lead")

        for lead in [lead_pending, lead_replied]:
            append_lead("example-client", lead)
            append_assistant_run("example-client", _make_run(lead))

        update_lead_status("example-client", lead_pending.lead_id, LeadStatus.awaiting_approval)
        update_lead_status("example-client", lead_replied.lead_id, LeadStatus.replied)

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        captured = capsys.readouterr()
        assert "Pending Lead" in captured.out
        assert "Replied Lead" not in captured.out

    def test_skips_lead_with_no_run(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main

        lead = _make_lead(name="No Run Lead")
        append_lead("example-client", lead)
        update_lead_status("example-client", lead.lead_id, LeadStatus.awaiting_approval)
        # Deliberately do NOT add an AssistantRun

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        captured = capsys.readouterr()
        assert "SKIP" in captured.err

    def test_skips_run_without_draft(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main

        lead = _make_lead(name="No Draft Lead")
        append_lead("example-client", lead)
        run = _make_run(lead, with_draft=False)
        # Manually override new_status to spam so draft_only_for_genuine passes
        import uuid as _uuid
        from lead_hub.schemas.assistant_workflow import (
            EscalationCheck, EscalationSeverity, LeadClassification,
            Classification, Confidence, AssistantRun,
        )
        esc = EscalationCheck(
            escalation_required=False, severity=EscalationSeverity.none,
            reasons=[], operator_summary="", suggested_operator_action="",
        )
        cls_spam = LeadClassification(
            classification=Classification.spam,
            confidence=Confidence.high,
            summary="Spam",
            recommended_next_status=LeadStatus.spam,
            risk_flags=[],
            escalation_required=False,
            escalation_reason="",
        )
        spam_run = AssistantRun(
            run_id=str(_uuid.uuid4()),
            lead_id=lead.lead_id,
            client_id="example-client",
            processed_at=_NOW,
            adapter="dry-run-v1",
            escalation_check=esc,
            classification=cls_spam,
            draft_reply=None,
            new_status=LeadStatus.spam,
        )
        append_assistant_run("example-client", spam_run)
        update_lead_status("example-client", lead.lead_id, LeadStatus.awaiting_approval)

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        captured = capsys.readouterr()
        assert "SKIP" in captured.err

    def test_multiple_pending_leads_all_notified(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main

        for i in range(3):
            lead = _make_lead(name=f"Lead {i}", message=f"EICR enquiry {i}")
            append_lead("example-client", lead)
            append_assistant_run("example-client", _make_run(lead))
            update_lead_status("example-client", lead.lead_id, LeadStatus.awaiting_approval)

        rc = main(["example-client", "--dry-run"])
        assert rc == 0

        events = read_audit_events("example-client")
        notification_events = [e for e in events if e.kind == AuditEventKind.notification_sent]
        assert len(notification_events) == 3

    def test_second_run_skips_already_notified_draft(self, tmp_state, config, capsys):
        from lead_hub.notify_approvals import main
        self._setup_lead_with_run("example-client")

        assert main(["example-client", "--dry-run"]) == 0
        assert main(["example-client", "--dry-run"]) == 0

        captured = capsys.readouterr()
        assert "already sent" in captured.err

        events = read_audit_events("example-client")
        notification_events = [e for e in events if e.kind == AuditEventKind.notification_sent]
        assert len(notification_events) == 1
