"""Detect and configure corporate CA certificates for Claude Code (Node.js).

On macOS: extracts certs from the System and login keychains.
On Linux: uses /etc/ssl/certs/ca-certificates.crt or /etc/pki/tls/certs/ca-bundle.crt.
On Windows: exports from the Windows certificate store.

Sets NODE_EXTRA_CA_CERTS in the user's shell profile so Claude Code can
connect through corporate TLS-intercepting proxies.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

CA_BUNDLE_PATH = Path.home() / ".enterprise-adk" / "ca-bundle.pem"


def setup_ca_certs() -> bool:
    """Extract CA certs and configure NODE_EXTRA_CA_CERTS. Returns True if successful."""
    system = platform.system()

    console.print("  [bold]Detecting corporate CA certificates…[/bold]")

    bundle = _extract_certs(system)
    if not bundle:
        console.print("  [yellow]![/yellow] Could not extract CA certs — Claude Code may fail behind a corporate proxy.")
        console.print("  [dim]Set manually: export NODE_EXTRA_CA_CERTS=/path/to/ca-bundle.crt[/dim]")
        return False

    # Write the bundle
    CA_BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CA_BUNDLE_PATH.write_text(bundle, encoding="utf-8")
    console.print(f"  [green]✓[/green] CA bundle written: {CA_BUNDLE_PATH}")

    # Set for the current process (so Claude Code launched from this shell inherits it)
    os.environ["NODE_EXTRA_CA_CERTS"] = str(CA_BUNDLE_PATH)

    # Persist to shell profile
    persisted = _persist_to_shell_profile()
    if persisted:
        console.print(f"  [green]✓[/green] NODE_EXTRA_CA_CERTS added to {persisted}")
        console.print("  [dim]Run: source ~/.zshrc  (or open a new terminal)[/dim]")
    else:
        console.print(f"  [yellow]![/yellow] Add this to your shell profile manually:")
        console.print(f"  [dim]  export NODE_EXTRA_CA_CERTS={CA_BUNDLE_PATH}[/dim]")

    return True


def already_configured() -> bool:
    """Return True if NODE_EXTRA_CA_CERTS is already set and the file exists."""
    val = os.environ.get("NODE_EXTRA_CA_CERTS", "")
    return bool(val) and Path(val).exists()


# ── Platform extractors ───────────────────────────────────────────────────────

def _extract_certs(system: str) -> str | None:
    if system == "Darwin":
        return _extract_macos()
    if system == "Linux":
        return _extract_linux()
    if system == "Windows":
        return _extract_windows()
    return None


def _extract_macos() -> str | None:
    """Export PEM certs from macOS System and login keychains."""
    keychains = [
        "/Library/Keychains/System.keychain",
        "/System/Library/Keychains/SystemRootCertificates.keychain",
    ]
    parts: list[str] = []
    for kc in keychains:
        if not Path(kc).exists():
            continue
        result = subprocess.run(  # noqa: S603 S607
            ["security", "find-certificate", "-a", "-p", kc],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts.append(result.stdout.strip())

    return "\n".join(parts) if parts else None


def _extract_linux() -> str | None:
    """Use the system CA bundle on Linux."""
    candidates = [
        "/etc/ssl/certs/ca-certificates.crt",   # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",      # RHEL/CentOS
        "/etc/ssl/ca-bundle.pem",                # OpenSUSE
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def _extract_windows() -> str | None:
    """Export certs from Windows certificate store via PowerShell."""
    ps_script = (
        "Get-ChildItem Cert:\\LocalMachine\\Root | "
        "ForEach-Object { "
        "  $bytes = $_.Export('Cert'); "
        "  $b64 = [Convert]::ToBase64String($bytes, 'InsertLineBreaks'); "
        "  '-----BEGIN CERTIFICATE-----'; $b64; '-----END CERTIFICATE-----' "
        "}"
    )
    result = subprocess.run(  # noqa: S603 S607
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _persist_to_shell_profile() -> Path | None:
    """Add NODE_EXTRA_CA_CERTS to the user's environment. Returns a Path on Unix or None on Windows."""
    if platform.system() == "Windows":
        _persist_windows_env()
        return None
    return _persist_unix_shell_profile()


def _persist_windows_env() -> None:
    """Set NODE_EXTRA_CA_CERTS as a persistent user environment variable on Windows."""
    result = subprocess.run(  # noqa: S603 S607
        ["setx", "NODE_EXTRA_CA_CERTS", str(CA_BUNDLE_PATH)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  [green]✓[/green] NODE_EXTRA_CA_CERTS set in user environment (restart terminal to apply)")
    else:
        console.print("  [yellow]![/yellow] Could not set env var automatically. Run in cmd.exe:")
        console.print(f"  [dim]  setx NODE_EXTRA_CA_CERTS \"{CA_BUNDLE_PATH}\"[/dim]")


def _persist_unix_shell_profile() -> Path | None:
    """Add NODE_EXTRA_CA_CERTS export to the user's shell profile. Returns the path used."""
    export_line = f'export NODE_EXTRA_CA_CERTS="{CA_BUNDLE_PATH}"'

    candidates: list[Path] = []
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        candidates = [Path.home() / ".zshrc", Path.home() / ".zprofile"]
    elif "bash" in shell:
        candidates = [Path.home() / ".bashrc", Path.home() / ".bash_profile"]
    else:
        candidates = [
            Path.home() / ".zshrc",
            Path.home() / ".bashrc",
            Path.home() / ".profile",
        ]

    for profile in candidates:
        existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
        if "NODE_EXTRA_CA_CERTS" in existing:
            lines = existing.splitlines()
            new_lines = [
                export_line if "NODE_EXTRA_CA_CERTS" in line else line
                for line in lines
            ]
            profile.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return profile
        with profile.open("a", encoding="utf-8") as f:
            f.write(f"\n# Enterprise ADK — corporate CA for Claude Code\n{export_line}\n")
        return profile

    return None
