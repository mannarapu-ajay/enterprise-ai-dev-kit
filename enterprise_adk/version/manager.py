"""Version lock management and GitHub release tag fetching."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VERSION_LOCK = "version.lock"
_AI_DEV_KIT_TAGS_API = "https://api.github.com/repos/databricks-solutions/ai-dev-kit/tags"
_AI_DEV_KIT_REPO     = "https://github.com/databricks-solutions/ai-dev-kit"


class VersionManager:
    """Read / write the version.lock file inside .enterprise-adk/."""

    def __init__(self, state_dir: Path) -> None:
        self.lock_path = state_dir / VERSION_LOCK

    # ── public API ────────────────────────────────────────────────────────────

    def read(self) -> dict:
        if self.lock_path.exists():
            return json.loads(self.lock_path.read_text(encoding="utf-8"))
        return {}

    def write(self, data: dict) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def stamp_install(
        self,
        *,
        enterprise_adk: str,
        ai_dev_kit: str,
        enterprise_skills: str,
        workspace_url: str = "",
    ) -> None:
        self.write({
            "enterprise_adk": enterprise_adk,
            "ai_dev_kit": ai_dev_kit,
            "enterprise_skills": enterprise_skills,
            "databricks_workspace": workspace_url,
            "installed_at": _now_iso(),
        })

    def update_field(self, **kwargs: str) -> None:
        current = self.read()
        current.update(kwargs)
        current["updated_at"] = _now_iso()
        self.write(current)

    def get(self, field: str, default: str = "") -> str:
        return self.read().get(field, default)


# ── tag fetching ──────────────────────────────────────────────────────────────

def fetch_latest_ai_dev_kit_tag() -> Optional[str]:
    """Return the latest semver tag from ai-dev-kit, or None on failure."""
    tag = _fetch_via_api()
    if tag:
        return tag
    return _fetch_via_git()


def compare_versions(current: str, latest: str) -> bool:
    """Return True when latest is strictly newer than current."""
    return _parse(latest) > _parse(current)


# ── internals ─────────────────────────────────────────────────────────────────

def _fetch_via_api() -> Optional[str]:
    try:
        req = urllib.request.Request(
            _AI_DEV_KIT_TAGS_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "enterprise-adk",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            tags: list[dict] = json.loads(resp.read())
        for tag in tags:
            name = tag.get("name", "")
            if re.match(r"^v?\d+\.\d+", name):
                return name
    except Exception:
        pass
    return None


def _fetch_via_git() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-v:refname", _AI_DEV_KIT_REPO],
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.splitlines():
            ref = line.split("\t")[-1]
            if ref.endswith("^{}"):
                continue
            tag = ref.replace("refs/tags/", "")
            if re.match(r"^v?\d+\.\d+", tag):
                return tag
    except Exception:
        pass
    return None


def _parse(version: str) -> tuple[int, ...]:
    v = version.lstrip("v")
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
