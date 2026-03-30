"""Hatchling build hook — registers the branded CLI entry point from enterprise_config.yaml.

When the enterprise team sets:
    enterprise:
      cli_command: blackstraw

pip install will create BOTH:
    enterprise-adk   → enterprise_adk.cli:main
    blackstraw-adk   → enterprise_adk.cli:main
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        cli_command = _read_cli_command()
        if cli_command and cli_command != "enterprise":
            build_data.setdefault("shared_scripts", {})[f"{cli_command}-adk"] = (
                "enterprise_adk.cli:main"
            )


def _read_cli_command() -> str:
    config_path = Path(__file__).parent / "enterprise_adk" / "enterprise_config.yaml"
    if not config_path.exists():
        return ""
    try:
        import yaml
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return data.get("enterprise", {}).get("cli_command", "")
    except Exception:
        return ""
