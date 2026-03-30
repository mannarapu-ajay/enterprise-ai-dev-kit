"""Write MCP config and Claude settings files — exactly like ai-dev-kit does.

Project scope  → .mcp.json + .claude/settings.json
Global scope   → ~/.claude.json + ~/.claude/settings.json
"""

from __future__ import annotations

import json
from pathlib import Path

from enterprise_adk.setup import MCP_ENTRY, REPO_DIR, VENV_PYTHON

_UPDATE_CHECK_SCRIPT = REPO_DIR / ".claude-plugin" / "check_update.sh"

import platform as _platform
_HOOK_COMMAND = (
    f"powershell -NoProfile -File \"{REPO_DIR / '.claude-plugin' / 'check_update.ps1'}\""
    if _platform.system() == "Windows"
    else f"bash {_UPDATE_CHECK_SCRIPT}"
)


def write_mcp_config(base_dir: Path, profile: str = "DEFAULT", scope: str = "project") -> Path:
    """Write .mcp.json (project) or ~/.claude.json (global) with MCP server definition."""
    payload = {
        "mcpServers": {
            "databricks": {
                "command": str(VENV_PYTHON),
                "args": [str(MCP_ENTRY)],
                "defer_loading": True,
                "env": {
                    "DATABRICKS_CONFIG_PROFILE": profile,
                },
            }
        }
    }

    if scope == "global":
        config_path = Path.home() / ".claude.json"
    else:
        config_path = base_dir / ".mcp.json"

    # Merge into existing file rather than overwrite
    existing: dict = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    existing.setdefault("mcpServers", {})["databricks"] = payload["mcpServers"]["databricks"]
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return config_path


def write_claude_settings(base_dir: Path, scope: str = "project") -> Path:
    """Write .claude/settings.json with the SessionStart update-check hook."""
    if scope == "global":
        settings_path = Path.home() / ".claude" / "settings.json"
    else:
        settings_path = base_dir / ".claude" / "settings.json"

    settings_path.parent.mkdir(parents=True, exist_ok=True)

    hook_entry = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": _HOOK_COMMAND,
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
    }

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    # Merge hooks without clobbering other settings
    existing.setdefault("hooks", {})["SessionStart"] = hook_entry["hooks"]["SessionStart"]
    settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return settings_path
