"""Check and auto-install prerequisites: git, uv, databricks CLI."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys

from rich.console import Console

console = Console()

_IS_WINDOWS = platform.system() == "Windows"

_UV_INSTALL_CMD_UNIX    = "curl -LsSf https://astral.sh/uv/install.sh | sh"
_UV_INSTALL_CMD_WIN_PS  = "powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
_DB_INSTALL_CMD_UNIX    = "curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh"
_DB_INSTALL_CMD_WIN_PS  = "winget install Databricks.DatabricksCLI"


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    return subprocess.run(cmd, capture_output=True, text=True, **kw)  # noqa: S603


def _install_uv_windows() -> bool:
    """Install uv on Windows via PowerShell."""
    r = subprocess.run(  # noqa: S603 S607
        ["powershell", "-ExecutionPolicy", "ByPass", "-Command",
         "irm https://astral.sh/uv/install.ps1 | iex"],
        capture_output=False,
    )
    return r.returncode == 0 and bool(shutil.which("uv"))


def _install_databricks_windows() -> bool:
    """Install Databricks CLI on Windows via winget."""
    r = subprocess.run(  # noqa: S603 S607
        ["winget", "install", "Databricks.DatabricksCLI", "--accept-package-agreements"],
        capture_output=False,
    )
    return r.returncode == 0 and bool(shutil.which("databricks"))


def _check_git() -> bool:
    if shutil.which("git"):
        v = _run(["git", "--version"]).stdout.strip()
        console.print(f"  [green]✓[/green] {v}")
        return True
    console.print("  [red]✗[/red] git not found. Install from https://git-scm.com and retry.")
    return False


def _check_uv() -> bool:
    if shutil.which("uv"):
        v = _run(["uv", "--version"]).stdout.strip()
        console.print(f"  [green]✓[/green] {v}")
        return True
    console.print("  [yellow]![/yellow] uv not found — installing…")
    if _IS_WINDOWS:
        ok, manual_cmd = _install_uv_windows(), _UV_INSTALL_CMD_WIN_PS
    else:
        r = subprocess.run(["bash", "-c", _UV_INSTALL_CMD_UNIX], capture_output=False)  # noqa: S603 S607
        ok, manual_cmd = r.returncode == 0 and bool(shutil.which("uv")), _UV_INSTALL_CMD_UNIX
    if ok:
        console.print("  [green]✓[/green] uv installed")
        return True
    console.print(f"  [red]✗[/red] uv install failed. Run manually:\n    {manual_cmd}")
    return False


def _check_databricks() -> bool:
    if shutil.which("databricks"):
        raw = _run(["databricks", "--version"])
        v = (raw.stdout or raw.stderr).strip().splitlines()[0]
        console.print(f"  [green]✓[/green] databricks CLI: {v}")
        return True
    console.print("  [yellow]![/yellow] Databricks CLI not found — installing…")
    if _IS_WINDOWS:
        ok, manual_cmd = _install_databricks_windows(), _DB_INSTALL_CMD_WIN_PS
    else:
        r = subprocess.run(["bash", "-c", _DB_INSTALL_CMD_UNIX], capture_output=False)  # noqa: S603 S607
        ok, manual_cmd = r.returncode == 0 and bool(shutil.which("databricks")), _DB_INSTALL_CMD_UNIX
    if ok:
        console.print("  [green]✓[/green] Databricks CLI installed")
        return True
    console.print(f"  [red]✗[/red] Databricks CLI install failed. Run manually:\n    {manual_cmd}")
    return False


def check_and_fix() -> bool:
    """Return True only when all required tools are present (after auto-install attempts)."""
    console.print("\n[bold cyan]Checking prerequisites…[/bold cyan]")
    results = [_check_git(), _check_uv(), _check_databricks()]
    return all(results)
