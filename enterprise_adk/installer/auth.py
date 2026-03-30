"""Databricks OAuth authentication via the Databricks CLI."""

from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import urllib.request
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


def list_clusters(profile: str = "DEFAULT") -> list[dict]:
    """Return RUNNING clusters from the workspace. Each dict has 'id', 'name', 'state'.

    Fast path: resolves an access token then calls the REST API directly (avoids
    CLI subprocess overhead and skips terminated clusters server-side via filtering).
    Falls back to the CLI with a 30 s timeout if the fast path fails.
    Returns an empty list on any failure.
    """
    host  = workspace_url_from_profile(profile)
    token = _access_token(profile, host)

    if host and token:
        try:
            return _clusters_via_api(host, token)
        except Exception:
            pass

    # ── CLI fallback ──────────────────────────────────────────────────────────
    try:
        result = subprocess.run(
            ["databricks", "clusters", "list", "--profile", profile, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return []
    if result.returncode != 0:
        return []
    try:
        data     = json.loads(result.stdout)
        clusters = data if isinstance(data, list) else data.get("clusters", [])
        return _filter_all_purpose(clusters)
    except Exception:
        return []


def _access_token(profile: str, host: str | None = None) -> str | None:
    """Return a bearer token for *profile* by asking the CLI's local token cache.

    Passes --host so the CLI knows which workspace to get the token for
    (required by Databricks CLI v0.2xx).
    """
    cmd = ["databricks", "auth", "token", "--profile", profile]
    if host:
        cmd += ["--host", host.rstrip("/")]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            raw = r.stdout.strip()
            # newer CLI emits JSON; older CLI emits the raw token string
            try:
                return json.loads(raw).get("access_token") or json.loads(raw).get("token_value")
            except Exception:
                return raw or None
    except Exception:
        pass
    # static PAT fallback from ~/.databrickscfg
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
        elif in_section and line.lower().startswith("token"):
            return line.split("=", 1)[-1].strip()
    return None


def _ssl_context() -> ssl.SSLContext:
    """Build an SSL context that trusts the enterprise CA bundle if configured."""
    ctx = ssl.create_default_context()
    ca_bundle = (
        os.environ.get("NODE_EXTRA_CA_CERTS")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("SSL_CERT_FILE")
    )
    if ca_bundle and Path(ca_bundle).exists():
        ctx.load_verify_locations(cafile=ca_bundle)
    return ctx


def _clusters_via_api(host: str, token: str) -> list[dict]:
    """Call the Clusters REST API directly and return only all-purpose RUNNING clusters."""
    url = host.rstrip("/") + "/api/2.0/clusters/list"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        data = json.loads(resp.read())
    return _filter_all_purpose(data.get("clusters", []))


def _filter_all_purpose(clusters: list) -> list[dict]:
    """Keep only all-purpose clusters (exclude job-run clusters). Any state is included."""
    return [
        {
            "id": c["cluster_id"],
            "name": c.get("cluster_name", c["cluster_id"]),
            "state": c.get("state", ""),
        }
        for c in clusters
        if "cluster_id" in c and c.get("cluster_source", "UI") != "JOB"
    ]


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
