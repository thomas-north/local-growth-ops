"""
lead_hub.telegram_approval
~~~~~~~~~~~~~~~~~~~~~~~~~~
Format and send operator approval notifications via Telegram Bot API.

Approval notifications are sent when a lead reaches ``awaiting_approval`` status
and a DraftReply has been generated. The operator reviews the message and takes
manual action — nothing is sent to a customer automatically.

Token / chat ID resolution
--------------------------
Bot token:  ``TELEGRAM_BOT_TOKEN`` env var (required for live sends).
Chat ID:    ``TELEGRAM_CHAT_ID`` env var, then ``config.approval.telegram_chat_id``.

In dry-run mode neither is required. Tests must patch ``send_telegram_message``
so no real network calls are made.

PII in messages
---------------
Only the lead's name and a short excerpt of their message are included.
Email addresses and phone numbers are intentionally omitted from notifications
to minimise personal data passing through third-party chat infrastructure.
"""

from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from lead_hub.schemas.assistant_workflow import AssistantRun
from lead_hub.schemas.client_config import ClientAssistantConfig
from lead_hub.schemas.lead import NormalizedLead

_TELEGRAM_API = "https://api.telegram.org"
_EXCERPT_LENGTH = 300


class TelegramSendError(RuntimeError):
    """Raised when the Telegram Bot API call fails."""


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


def format_approval_message(
    lead: NormalizedLead,
    run: AssistantRun,
    config: ClientAssistantConfig,
) -> str:
    """
    Build the full text of an operator approval notification.

    Intentionally omits lead email and phone number to minimise PII in
    third-party chat infrastructure. The operator can look up full contact
    details in the JSONL state file if needed.
    """
    draft = run.draft_reply
    if draft is None:
        raise ValueError(
            f"Cannot format approval message: lead {lead.lead_id!r} has no draft reply."
        )

    cls = run.classification
    esc = run.escalation_check

    # Excerpt the lead message — no full PII
    excerpt = (lead.message or "").strip()
    if len(excerpt) > _EXCERPT_LENGTH:
        excerpt = excerpt[:_EXCERPT_LENGTH] + "…"

    assumptions_text = (
        "\n".join(f"  • {a}" for a in draft.assumptions)
        if draft.assumptions
        else "  (none)"
    )
    questions_text = (
        "\n".join(f"  • {q}" for q in draft.questions_for_lead)
        if draft.questions_for_lead
        else "  (none)"
    )
    risk_text = (
        "\n".join(f"  • {r}" for r in cls.risk_flags)
        if cls.risk_flags
        else "  (none)"
    )

    escalation_section = ""
    if esc.escalation_required:
        escalation_section = textwrap.dedent(f"""\
            ⚠️  ESCALATION FLAGS
            {risk_text}
            Severity: {esc.severity.value}
            Action: {esc.suggested_operator_action}

            """)

    lines = textwrap.dedent(f"""\
        ═══════════════════════════════════
        OPERATOR APPROVAL REQUIRED
        Client: {config.business.name}
        Lead ID: {lead.lead_id[:8]}
        ═══════════════════════════════════

        LEAD
        Name:    {lead.name}
        Message: {excerpt}

        CLASSIFICATION
        Result:     {cls.classification.value}
        Confidence: {cls.confidence.value}
        Summary:    {cls.summary}

        {escalation_section}DRAFT REPLY
        Subject: {draft.draft_subject}
        ───────────────────────────────────
        {draft.draft_body}
        ───────────────────────────────────

        ASSUMPTIONS
        {assumptions_text}

        QUESTIONS FOR LEAD
        {questions_text}

        OPERATOR NOTES
        {draft.operator_notes}

        ═══════════════════════════════════
        ⚠️  Operator approval required before any message is sent to the lead.
        Approve, edit, or escalate using the ops commands below.
        Run ID: {run.run_id[:8]}
        ═══════════════════════════════════
        """)

    return lines


# ---------------------------------------------------------------------------
# HTTP sender (patched in tests — never call in tests)
# ---------------------------------------------------------------------------


def send_telegram_message(text: str, chat_id: str, bot_token: str) -> None:
    """
    POST a plain-text message to the Telegram Bot API sendMessage endpoint.

    Raises TelegramSendError on HTTP or network failure.
    """
    url = f"{_TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 201):
                raise TelegramSendError(
                    f"Telegram API returned status {resp.status}"
                )
    except urllib.error.HTTPError as exc:
        raise TelegramSendError(
            f"Telegram API HTTP error {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise TelegramSendError(
            f"Telegram API network error: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


def resolve_bot_token() -> Optional[str]:
    """Return TELEGRAM_BOT_TOKEN from env, or None if unset."""
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def resolve_chat_id(config: ClientAssistantConfig) -> Optional[str]:
    """
    Return the Telegram chat ID for operator notifications.

    Resolution order:
    1. TELEGRAM_CHAT_ID env var
    2. config.approval.telegram_chat_id (may be empty string)
    """
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if env_chat_id:
        return env_chat_id
    config_chat_id = (config.approval.telegram_chat_id or "").strip()
    if config_chat_id:
        return config_chat_id
    return None
