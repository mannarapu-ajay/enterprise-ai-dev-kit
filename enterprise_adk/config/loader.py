"""Config loader — reads the package-embedded enterprise_config.yaml.

The config lives at enterprise_adk/enterprise_config.yaml.
The enterprise team edits this file once when forking the repo.
Data engineers install the package and never touch config directly.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from enterprise_adk.config.models import AppConfig

_PKG_CONFIG = Path(__file__).parent.parent / "enterprise_config.yaml"


def load_config() -> AppConfig:
    """Load config from the embedded enterprise_config.yaml."""
    if _PKG_CONFIG.exists():
        data = yaml.safe_load(_PKG_CONFIG.read_text(encoding="utf-8")) or {}
        return AppConfig.model_validate(data)
    return AppConfig()
