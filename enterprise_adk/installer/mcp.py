"""MCP server setup — thin wrapper over enterprise_adk.setup and enterprise_adk.mcp."""

from __future__ import annotations

from pathlib import Path

import enterprise_adk.mcp as _mcp
from enterprise_adk.setup import ensure_mcp_server, update_repo


def setup(project_root: Path, profile: str = "DEFAULT", version: str = "main") -> tuple[Path, Path]:
    """Ensure MCP server venv is ready at `version` and write project config files.

    Returns (mcp_config_path, claude_settings_path).
    """
    ensure_mcp_server(version=version)
    mcp_path      = _mcp.write_mcp_config(project_root, profile=profile, scope="project")
    settings_path = _mcp.write_claude_settings(project_root, scope="project")
    return mcp_path, settings_path


def update(version: str = "main") -> str | None:
    """Pull ai-dev-kit at `version` and reinstall packages. Returns new version string."""
    return update_repo(version=version)
