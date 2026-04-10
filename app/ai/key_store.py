"""Secure API-key persistence for cloud LLM providers.

Keys are stored in a user-level JSON file (~/.assistant_editor_pro/api_keys.json)
with restrictive file permissions (owner-only read/write).
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

_CONFIG_DIR = Path.home() / ".assistant_editor_pro"
_KEYS_FILE = _CONFIG_DIR / "api_keys.json"


def _read() -> dict[str, str]:
    if not _KEYS_FILE.exists():
        return {}
    try:
        return json.loads(_KEYS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict[str, str]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _KEYS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        _KEYS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def get_key(provider: str) -> str:
    """Return the stored API key for *provider*, or empty string."""
    return _read().get(provider, "")


def set_key(provider: str, key: str) -> None:
    """Persist an API key for *provider*. Empty string removes it."""
    data = _read()
    if key:
        data[provider] = key
    else:
        data.pop(provider, None)
    _write(data)


def all_keys() -> dict[str, str]:
    """Return a copy of every stored key, keyed by provider name."""
    return dict(_read())
