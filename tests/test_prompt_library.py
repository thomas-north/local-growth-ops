"""
tests/test_prompt_library.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic validation of the Openclaw prompt library.

Checks:
- all required prompt and example files exist
- every JSON example file is valid JSON
- output examples contain the required output keys for their prompt
- safety-critical phrases are present in instructions.md / prompt files
- no real-client-looking data appears in example files

No network calls, no Openclaw API calls, no model inference.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_AGENT_DIR = Path(__file__).parent.parent / "openclaw" / "agents" / "followup-assistant"
_PROMPTS_DIR = _AGENT_DIR / "prompts"
_EXAMPLES_DIR = _AGENT_DIR / "examples"

# ---------------------------------------------------------------------------
# Required files
# ---------------------------------------------------------------------------

REQUIRED_PROMPT_FILES = [
    "classify.md",
    "draft_reply.md",
    "draft_followup.md",
    "escalation.md",
    "weekly_report.md",
]

REQUIRED_EXAMPLE_FILES = [
    "classify_input.json",
    "classify_output.json",
    "draft_reply_input.json",
    "draft_reply_output.json",
    "draft_followup_input.json",
    "draft_followup_output.json",
    "escalation_input.json",
    "escalation_output.json",
    "weekly_report_input.json",
    "weekly_report_output.json",
]

# Required keys in each output example
REQUIRED_OUTPUT_KEYS: dict[str, list[str]] = {
    "classify_output.json": [
        "classification",
        "confidence",
        "summary",
        "recommended_next_status",
        "risk_flags",
        "escalation_required",
        "escalation_reason",
    ],
    "draft_reply_output.json": [
        "draft_subject",
        "draft_body",
        "assumptions",
        "questions_for_lead",
        "operator_notes",
        "approval_required",
    ],
    "draft_followup_output.json": [
        "draft_body",
        "followup_number",
        "operator_notes",
        "approval_required",
        "should_stop_followups",
    ],
    "escalation_output.json": [
        "escalation_required",
        "severity",
        "reasons",
        "operator_summary",
        "suggested_operator_action",
    ],
    "weekly_report_output.json": [
        "report_title",
        "period_summary",
        "lead_counts",
        "wins_or_likely_wins",
        "stale_leads",
        "recommended_actions",
        "client_facing_summary",
        "operator_notes",
    ],
}

# Safety-critical phrases that must appear somewhere in the prompt library
SAFETY_PHRASES = [
    # No unsupervised sending
    ("no exceptions in the MVP", "instructions.md"),
    # Do not invent prices
    ("invent prices", "instructions.md"),
    # Do not promise availability/timescales
    ("timescales", "instructions.md"),
    # Escalate complaints, disputes, safety
    ("complaint", "instructions.md"),
    ("safety concern", "instructions.md"),
    # Approval required
    ("approval_required", "prompts/draft_reply.md"),
    ("approval_required", "prompts/draft_followup.md"),
    # Source of truth
    ("source of truth", "instructions.md"),
]


# ---------------------------------------------------------------------------
# Tests: file existence
# ---------------------------------------------------------------------------


class TestRequiredFilesExist:
    def test_instructions_md_exists(self):
        assert (_AGENT_DIR / "instructions.md").is_file(), \
            "instructions.md is missing"

    def test_agent_readme_exists(self):
        assert (_AGENT_DIR / "README.md").is_file(), \
            "followup-assistant/README.md is missing"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPT_FILES)
    def test_prompt_file_exists(self, filename):
        assert (_PROMPTS_DIR / filename).is_file(), \
            f"prompts/{filename} is missing"

    @pytest.mark.parametrize("filename", REQUIRED_EXAMPLE_FILES)
    def test_example_file_exists(self, filename):
        assert (_EXAMPLES_DIR / filename).is_file(), \
            f"examples/{filename} is missing"


# ---------------------------------------------------------------------------
# Tests: JSON validity
# ---------------------------------------------------------------------------


class TestExampleJsonValid:
    @pytest.mark.parametrize("filename", REQUIRED_EXAMPLE_FILES)
    def test_example_is_valid_json(self, filename):
        path = _EXAMPLES_DIR / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"examples/{filename} is not valid JSON: {exc}")
        assert isinstance(data, dict), \
            f"examples/{filename} must be a JSON object, got {type(data).__name__}"


# ---------------------------------------------------------------------------
# Tests: output key completeness
# ---------------------------------------------------------------------------


class TestOutputExampleKeys:
    @pytest.mark.parametrize("filename,required_keys", REQUIRED_OUTPUT_KEYS.items())
    def test_output_example_has_required_keys(self, filename, required_keys):
        path = _EXAMPLES_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in required_keys if k not in data]
        assert not missing, \
            f"examples/{filename} is missing required keys: {missing}"


# ---------------------------------------------------------------------------
# Tests: output example value constraints
# ---------------------------------------------------------------------------


class TestOutputExampleValues:
    def test_classify_output_classification_is_valid(self):
        valid = {
            "genuine_lead", "spam", "out_of_scope",
            "needs_human_review", "complaint_or_dispute", "urgent_or_safety",
        }
        data = json.loads((_EXAMPLES_DIR / "classify_output.json").read_text())
        assert data["classification"] in valid, \
            f"classify_output.json classification {data['classification']!r} not in taxonomy"

    def test_classify_output_confidence_is_valid(self):
        data = json.loads((_EXAMPLES_DIR / "classify_output.json").read_text())
        assert data["confidence"] in {"high", "medium", "low"}

    def test_classify_output_escalation_required_is_bool(self):
        data = json.loads((_EXAMPLES_DIR / "classify_output.json").read_text())
        assert isinstance(data["escalation_required"], bool)

    def test_draft_reply_output_approval_required_is_true(self):
        data = json.loads((_EXAMPLES_DIR / "draft_reply_output.json").read_text())
        assert data["approval_required"] is True, \
            "draft_reply_output.json: approval_required must be true"

    def test_draft_followup_output_approval_required_is_true(self):
        data = json.loads((_EXAMPLES_DIR / "draft_followup_output.json").read_text())
        assert data["approval_required"] is True, \
            "draft_followup_output.json: approval_required must be true"

    def test_draft_followup_output_should_stop_is_bool(self):
        data = json.loads((_EXAMPLES_DIR / "draft_followup_output.json").read_text())
        assert isinstance(data["should_stop_followups"], bool)

    def test_escalation_output_escalation_required_is_bool(self):
        data = json.loads((_EXAMPLES_DIR / "escalation_output.json").read_text())
        assert isinstance(data["escalation_required"], bool)

    def test_escalation_output_severity_is_valid(self):
        data = json.loads((_EXAMPLES_DIR / "escalation_output.json").read_text())
        assert data["severity"] in {"critical", "high", "medium", "none"}

    def test_escalation_example_shows_escalation_required(self):
        """The example escalation case should require escalation."""
        data = json.loads((_EXAMPLES_DIR / "escalation_output.json").read_text())
        assert data["escalation_required"] is True

    def test_weekly_report_lead_counts_has_required_keys(self):
        data = json.loads((_EXAMPLES_DIR / "weekly_report_output.json").read_text())
        required = {"total", "genuine_leads", "spam", "out_of_scope",
                    "escalated", "won", "lost", "open"}
        counts = data.get("lead_counts", {})
        missing = required - counts.keys()
        assert not missing, f"weekly_report_output.json lead_counts missing: {missing}"


# ---------------------------------------------------------------------------
# Tests: safety language in prompt files
# ---------------------------------------------------------------------------


class TestSafetyLanguage:
    @pytest.mark.parametrize("phrase,relative_path", SAFETY_PHRASES)
    def test_safety_phrase_present(self, phrase, relative_path):
        path = _AGENT_DIR / relative_path
        content = path.read_text(encoding="utf-8").lower()
        assert phrase.lower() in content, \
            f"Safety phrase {phrase!r} not found in {relative_path}"

    def test_instructions_mentions_client_config_source_of_truth(self):
        content = (_AGENT_DIR / "instructions.md").read_text(encoding="utf-8")
        assert "source of truth" in content.lower()

    def test_draft_reply_prompt_mentions_approval_required_true(self):
        content = (_PROMPTS_DIR / "draft_reply.md").read_text(encoding="utf-8")
        assert "approval_required" in content
        assert "true" in content.lower()

    def test_escalation_prompt_mentions_bias_toward_escalation(self):
        content = (_PROMPTS_DIR / "escalation.md").read_text(encoding="utf-8")
        assert "bias" in content.lower() or "biases" in content.lower()

    def test_instructions_forbids_sending_without_approval(self):
        content = (_AGENT_DIR / "instructions.md").read_text(encoding="utf-8")
        # Must clearly state no unsupervised sending
        assert "without" in content and "approval" in content

    def test_weekly_report_prompt_separates_client_and_operator_output(self):
        content = (_PROMPTS_DIR / "weekly_report.md").read_text(encoding="utf-8")
        assert "client_facing_summary" in content
        assert "operator_notes" in content


# ---------------------------------------------------------------------------
# Tests: no real-client data in examples
# ---------------------------------------------------------------------------


class TestNoRealClientData:
    @pytest.mark.parametrize("filename", REQUIRED_EXAMPLE_FILES)
    def test_no_real_phone_numbers(self, filename):
        content = (_EXAMPLES_DIR / filename).read_text(encoding="utf-8")
        import re
        # UK mobile pattern: 07 followed by 9 digits
        real_mobile = re.compile(r"\b07\d{9}\b")
        assert not real_mobile.search(content), \
            f"examples/{filename} appears to contain a real UK mobile number"

    @pytest.mark.parametrize("filename", REQUIRED_EXAMPLE_FILES)
    def test_no_real_email_domains(self, filename):
        content = (_EXAMPLES_DIR / filename).read_text(encoding="utf-8")
        for domain in ("@gmail.com", "@hotmail.com", "@yahoo.com", "@outlook.com"):
            assert domain not in content, \
                f"examples/{filename} contains real email domain {domain!r}"
