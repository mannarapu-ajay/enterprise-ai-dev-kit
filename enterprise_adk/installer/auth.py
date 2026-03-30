"""Databricks OAuth authentication via the Databricks CLI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def oauth_login(workspace_url: str, profile: str = "DEFAULT") -> bool:
    """Open a browser for Databricks OAuth login. Returns True on success."""
    if not shutil.which("databricks"):
        console.print("  [red]✗[/red] databricks CLI not found — run prerequisites check first.")
        return False

    workspace_url = workspace_url.rstrip("/")
    console.print(f"  Opening browser for OAuth login → [cyan]{workspace_url}[/cyan]")

    result = subprocess.run(
        ["databricks", "auth", "login", "--host", workspace_url, "--profile", profile],
        capture_output=False,
    )
    return result.returncode == 0


def validate_connection(profile: str = "DEFAULT") -> bool:
    """Return True if the Databricks connection is working."""
    result = subprocess.run(
        ["databricks", "current-user", "me", "--profile", profile],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def workspace_url_from_profile(profile: str = "DEFAULT") -> Optional[str]:
    """Read the workspace host URL from ~/.databrickscfg."""
    cfg = Path.home() / ".databrickscfg"
    if not cfg.exists():
        return None

    in_section = False
    for line in cfg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == f"[{profile}]":
            in_section = True
        elif line.startswith("["):
            in_section = False
        elif in_section and line.lower().startswith("host"):
            return line.split("=", 1)[-1].strip()
    return None


def available_profiles() -> list[str]:
    """Return profile names found in ~/.databrickscfg."""
    cfg = Path.home() / ".databrickscfg"
    if not cfg.exists():
        return []
    profiles: list[str] = []
    for line in cfg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            profiles.append(line[1:-1])
    return profiles
