"""
lead_hub.config_loader
~~~~~~~~~~~~~~~~~~~~~~
Load and validate a client assistant config from
``clients/<client-slug>/config.yaml``.

Usage::

    from lead_hub.config_loader import load_client_config
    config = load_client_config("example-client")
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from lead_hub.schemas.client_config import ClientAssistantConfig

# Repo root is two levels up from this file (lead_hub/config_loader.py)
_REPO_ROOT = Path(__file__).parent.parent


def _client_config_path(client_slug: str) -> Path:
    return _REPO_ROOT / "clients" / client_slug / "config.yaml"


def load_client_config(client_slug: str) -> ClientAssistantConfig:
    """Load and validate the config for *client_slug*.

    Raises
    ------
    FileNotFoundError
        If ``clients/<client_slug>/config.yaml`` does not exist.
    ValueError
        If the YAML cannot be parsed.
    pydantic.ValidationError
        If the config does not satisfy the schema.
    """
    path = _client_config_path(client_slug)
    if not path.exists():
        raise FileNotFoundError(
            f"No config found for client {client_slug!r}. "
            f"Expected: {path}"
        )

    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML for {client_slug!r}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Config for {client_slug!r} must be a YAML mapping, got {type(data).__name__}"
        )

    return ClientAssistantConfig.model_validate(data)
