"""Clone ai-dev-kit at the configured version and set up the MCP server venv."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

INSTALL_DIR = Path.home() / ".enterprise-adk"
REPO_DIR    = INSTALL_DIR / "repo"
VENV_DIR    = INSTALL_DIR / ".venv"
VENV_PYTHON = (
    VENV_DIR / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else VENV_DIR / "bin" / "python"
)
MCP_ENTRY = REPO_DIR / "databricks-mcp-server" / "run_server.py"


def ensure_mcp_server(version: str = "main") -> None:
    """Clone/update repo at `version` and install the MCP server. Idempotent."""
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
        t = prog.add_task("Setting up MCP server…", total=None)
        _clone_or_update_repo(version=version)
        prog.update(t, description="Creating Python venv…")
        _create_venv()
        prog.update(t, description="Installing MCP server packages…")
        _install_packages()
        prog.update(t, completed=True)

    console.print("  [green]✓[/green] Databricks MCP server ready")
    console.print(f"  [dim]Server: {MCP_ENTRY}[/dim]")


def installed_version() -> str | None:
    """Return the version string from the cloned repo, or None."""
    for candidate in [REPO_DIR / "VERSION", REPO_DIR / "version.txt"]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()
    return None


def update_repo(version: str = "main") -> str | None:
    """Pull latest at `version` and reinstall packages. Returns new version."""
    _clone_or_update_repo(version=version, force=True)
    _install_packages()
    return installed_version()


# ── internal helpers ──────────────────────────────────────────────────────────

def _clone_or_update_repo(version: str = "main", *, force: bool = False) -> None:
    from enterprise_adk.config.loader import load_config
    repo_url = load_config().ai_dev_kit.repo

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    if REPO_DIR.exists() and not force:
        _git(["fetch", "--depth=1", "origin", version], cwd=REPO_DIR)
        _git(["reset", "--hard", "FETCH_HEAD"], cwd=REPO_DIR)
        return

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)

    _git([
        "clone", "-q", "--depth", "1",
        "--branch", version, "--single-branch",
        repo_url, str(REPO_DIR),
    ])


def _create_venv() -> None:
    if VENV_PYTHON.exists():
        return
    cmd = ["uv", "venv", "--python", "3.11", "--allow-existing", str(VENV_DIR)]
    if sys.platform in ("darwin", "win32"):
        cmd.append("--native-tls")
    _run(cmd)


def _install_packages() -> None:
    pkgs: list[str] = []
    for sub in ["databricks-tools-core", "databricks-mcp-server"]:
        p = REPO_DIR / sub
        if p.exists():
            pkgs.append(f"--editable={p}")
    if not pkgs:
        return

    cmd = ["uv", "pip", "install", "--python", str(VENV_PYTHON)]
    if sys.platform in ("darwin", "win32"):
        cmd.append("--native-tls")
    cmd.extend(pkgs)
    _run(cmd)


def _git(args: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(  # noqa: S603 S607
        ["git", *args], capture_output=True, text=True,
        cwd=str(cwd) if cwd else None,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{r.stderr}")


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stderr}")
