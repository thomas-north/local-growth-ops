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

    The validated config's ``client_id`` must match *client_slug*. A mismatch
    means the config file was placed in the wrong directory or its internal ID
    was changed, either of which is a misconfiguration.

    Raises
    ------
    FileNotFoundError
        If ``clients/<client_slug>/config.yaml`` does not exist.
    ValueError
        If the YAML cannot be parsed, is not a mapping, or the internal
        ``client_id`` does not match *client_slug*.
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

    config = ClientAssistantConfig.model_validate(data)

    if config.client_id != client_slug:
        raise ValueError(
            f"Config identity mismatch: loaded via slug {client_slug!r} but "
            f"config.client_id is {config.client_id!r}. "
            f"Move the config to clients/{config.client_id}/ or correct client_id."
        )

    return config
