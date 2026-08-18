"""Centralized selector and configuration loader.

Reads `app/selectors.yaml` at import time and provides attribute-style access
to selectors and operational settings.
"""

from __future__ import annotations

from pathlib import Path
import yaml

SELECTORS_FILE = Path(__file__).parent / "selectors.yaml"


class ConfigDict(dict):
    """Dict subclass supporting attribute-style access (e.g. SEL.results_feed.css_fallback)."""

    def __getattr__(self, key: str):
        try:
            val = self[key]
            if isinstance(val, dict) and not isinstance(val, ConfigDict):
                val = ConfigDict(val)
                self[key] = val
            return val
        except KeyError:
            raise AttributeError(f"Config has no attribute '{key}'")

    def __setattr__(self, key: str, value):
        self[key] = value


def load_config() -> ConfigDict:
    if not SELECTORS_FILE.exists():
        raise FileNotFoundError(f"Selector file not found: {SELECTORS_FILE}")
    with open(SELECTORS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ConfigDict(data)


SEL = load_config()
