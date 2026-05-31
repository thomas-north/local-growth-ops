"""
Tests for the client assistant config schema and loader.

All test data is fictional. No real client data or secrets are used.
"""

from __future__ import annotations

import copy
import textwrap
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from lead_hub.schemas.client_config import (
    AutoSendConfig,
    ClientAssistantConfig,
    FollowupConfig,
    RetentionConfig,
)

# ---------------------------------------------------------------------------
# Minimal valid fixture — keeps tests short and explicit
# ---------------------------------------------------------------------------

_VALID: dict = {
    "client_id": "example-client",
    "client_slug": "example-client",
    "business": {
        "name": "Bright Spark Electrical",
        "legal_name": "Bright Spark Electrical Ltd",
        "tagline": "Reliable domestic electricians",
        "description": "A fictional electrical contractor for testing.",
        "phone": "0113 000 0000",
        "email": "hello@example-client.invalid",
        "address_visible": False,
        "area": "South Leeds",
    },
    "services": [
        {"name": "Full rewire", "slug": "full-rewire"},
        {"name": "EV charger", "slug": "ev-charger"},
    ],
    "exclusions": ["Never quote fixed prices without owner approval"],
    "pricing_policy": "Do not quote specific prices.",
    "hours": {
        "monday_friday": "08:00–18:00",
        "saturday": "09:00–13:00",
        "sunday": "Closed",
    },
    "tone": {
        "style": "Friendly, plain-English",
        "length": "Two to three short paragraphs",
        "sign_off": "Tom, Bright Spark Electrical",
    },
    "approval": {
        "telegram_chat_id": "",
        "email": "",
    },
    "escalation_triggers": ["complaint or dispute"],
    "followup": {
        "first_followup_days": 3,
        "second_followup_days": 7,
        "max_followups": 2,
    },
    "auto_send": {
        "first_reply": False,
        "followups": False,
        "weekly_report": False,
    },
    "retention": {
        "lead_retention_days": 365,
        "delete_pii_after_days": 730,
    },
}


def _build(**overrides) -> dict:
    """Return a deep copy of _VALID with nested overrides applied."""
    data = copy.deepcopy(_VALID)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return data


def _valid() -> ClientAssistantConfig:
    return ClientAssistantConfig.model_validate(_VALID)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestValidConfig:
    def test_example_client_loads(self):
        cfg = _valid()
        assert cfg.client_id == "example-client"
        assert cfg.business.name == "Bright Spark Electrical"
        assert len(cfg.services) == 2

    def test_example_domain_email_accepted(self):
        """The .invalid TLD must be accepted (example domains are allowed)."""
        cfg = _valid()
        assert cfg.business.email == "hello@example-client.invalid"

    def test_approval_empty_strings_accepted(self):
        """Real approval contacts live in secrets; empty strings are valid."""
        cfg = _valid()
        assert cfg.approval.telegram_chat_id == ""
        assert cfg.approval.email == ""

    def test_weekly_report_auto_send_may_be_true(self):
        """weekly_report is not restricted by the MVP safety rule."""
        data = _build(auto_send={"first_reply": False, "followups": False, "weekly_report": True})
        cfg = ClientAssistantConfig.model_validate(data)
        assert cfg.auto_send.weekly_report is True

    def test_equal_followup_days_accepted(self):
        data = _build(followup={
            "first_followup_days": 5,
            "second_followup_days": 5,
            "max_followups": 1,
        })
        cfg = ClientAssistantConfig.model_validate(data)
        assert cfg.followup.first_followup_days == 5

    def test_zero_max_followups_accepted(self):
        data = _build(followup={
            "first_followup_days": 3,
            "second_followup_days": 7,
            "max_followups": 0,
        })
        cfg = ClientAssistantConfig.model_validate(data)
        assert cfg.followup.max_followups == 0


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    @pytest.mark.parametrize("field", [
        "client_id", "client_slug", "business", "services", "exclusions",
        "pricing_policy", "hours", "tone", "approval", "escalation_triggers",
        "followup", "auto_send", "retention",
    ])
    def test_missing_top_level_field_fails(self, field):
        data = copy.deepcopy(_VALID)
        del data[field]
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    @pytest.mark.parametrize("field", ["name", "legal_name", "description", "phone", "email", "area"])
    def test_missing_business_field_fails(self, field):
        data = copy.deepcopy(_VALID)
        del data["business"][field]
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    @pytest.mark.parametrize("field", ["monday_friday", "saturday", "sunday"])
    def test_missing_hours_field_fails(self, field):
        data = copy.deepcopy(_VALID)
        del data["hours"][field]
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    @pytest.mark.parametrize("field", ["style", "length", "sign_off"])
    def test_missing_tone_field_fails(self, field):
        data = copy.deepcopy(_VALID)
        del data["tone"][field]
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------


class TestSlugValidation:
    @pytest.mark.parametrize("bad_slug", [
        "Example-Client",  # uppercase
        "example_client",  # underscore
        "example client",  # space
        "-leading-hyphen",
        "trailing-hyphen-",
        "",
    ])
    def test_invalid_client_id_slug_fails(self, bad_slug):
        data = _build(client_id=bad_slug, client_slug=bad_slug)
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    def test_client_id_slug_mismatch_fails(self):
        data = _build(client_id="foo", client_slug="bar")
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "must match" in str(exc_info.value)

    @pytest.mark.parametrize("bad_slug", [
        "Full Rewire",   # space
        "full_rewire",   # underscore
        "FULL-REWIRE",   # uppercase
        "",
    ])
    def test_invalid_service_slug_fails(self, bad_slug):
        data = _build(services=[{"name": "Full rewire", "slug": bad_slug}])
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Duplicate service slugs
# ---------------------------------------------------------------------------


class TestDuplicateServiceSlugs:
    def test_duplicate_service_slug_fails(self):
        data = _build(services=[
            {"name": "Full rewire", "slug": "full-rewire"},
            {"name": "Full rewire again", "slug": "full-rewire"},
        ])
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "duplicate" in str(exc_info.value).lower()

    def test_empty_services_list_fails(self):
        data = _build(services=[])
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)


# ---------------------------------------------------------------------------
# MVP auto-send safety rule
# ---------------------------------------------------------------------------


class TestAutoSendSafetyRule:
    def test_first_reply_true_fails(self):
        data = _build(auto_send={"first_reply": True, "followups": False, "weekly_report": False})
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "first_reply" in str(exc_info.value)

    def test_followups_true_fails(self):
        data = _build(auto_send={"first_reply": False, "followups": True, "weekly_report": False})
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "followups" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Follow-up ordering
# ---------------------------------------------------------------------------


class TestFollowupOrdering:
    def test_second_before_first_fails(self):
        data = _build(followup={
            "first_followup_days": 7,
            "second_followup_days": 3,
            "max_followups": 2,
        })
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "second_followup_days" in str(exc_info.value)

    def test_zero_first_followup_days_fails(self):
        data = _build(followup={
            "first_followup_days": 0,
            "second_followup_days": 7,
            "max_followups": 2,
        })
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    def test_max_followups_too_high_fails(self):
        data = _build(followup={
            "first_followup_days": 3,
            "second_followup_days": 7,
            "max_followups": 6,
        })
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Retention ordering
# ---------------------------------------------------------------------------


class TestRetentionOrdering:
    def test_pii_before_lead_retention_fails(self):
        data = _build(retention={
            "lead_retention_days": 730,
            "delete_pii_after_days": 365,
        })
        with pytest.raises(ValidationError) as exc_info:
            ClientAssistantConfig.model_validate(data)
        assert "delete_pii_after_days" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------


class TestEmailValidation:
    @pytest.mark.parametrize("bad_email", [
        "notanemail",
        "@nodomain",
        "no-at-sign",
        "",
    ])
    def test_invalid_email_fails(self, bad_email):
        data = copy.deepcopy(_VALID)
        data["business"]["email"] = bad_email
        with pytest.raises(ValidationError):
            ClientAssistantConfig.model_validate(data)

    @pytest.mark.parametrize("good_email", [
        "hello@example-client.invalid",
        "contact@myshop.example",
        "tom@brightspark.co.uk",
    ])
    def test_valid_email_accepted(self, good_email):
        data = copy.deepcopy(_VALID)
        data["business"]["email"] = good_email
        cfg = ClientAssistantConfig.model_validate(data)
        assert cfg.business.email == good_email


# ---------------------------------------------------------------------------
# Load from real config.yaml on disk
# ---------------------------------------------------------------------------


class TestConfigLoader:
    def test_load_example_client_from_disk(self):
        from lead_hub.config_loader import load_client_config
        cfg = load_client_config("example-client")
        assert cfg.client_id == "example-client"
        assert cfg.business.name == "Bright Spark Electrical"

    def test_missing_client_raises_file_not_found(self):
        from lead_hub.config_loader import load_client_config
        with pytest.raises(FileNotFoundError, match="no-such-client"):
            load_client_config("no-such-client")


# ---------------------------------------------------------------------------
# validate_client CLI
# ---------------------------------------------------------------------------


class TestValidateClientCLI:
    def test_valid_client_exits_zero(self):
        from lead_hub.validate_client import main
        assert main(["example-client"]) == 0

    def test_missing_client_exits_one(self):
        from lead_hub.validate_client import main
        assert main(["no-such-client"]) == 1

    def test_no_args_exits_two(self):
        from lead_hub.validate_client import main
        assert main([]) == 2
