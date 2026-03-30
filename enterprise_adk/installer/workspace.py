"""Create and maintain the standard project workspace structure."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def create(
    project_root: Path,
    enterprise_name: str = "enterprise",
    workspace_url: str = "",
) -> None:
    """Create directory structure and starter files. Idempotent."""
    state_dir = f".{enterprise_name}-adk"
    _make_dirs(project_root, state_dir)
    _write_gitignore(project_root, state_dir)
    _write_generated_readme(project_root)
    _write_starter_template(project_root, enterprise_name)
    _write_metadata(project_root, state_dir, enterprise_name, workspace_url)


def _make_dirs(root: Path, state_dir: str) -> None:
    for d in [".claude/skills", f"{state_dir}/skills", "src/generated", "instruction-templates"]:
        (root / d).mkdir(parents=True, exist_ok=True)


def _write_gitignore(root: Path, state_dir: str) -> None:
    gi = root / ".gitignore"
    rules = [
        f"{state_dir}/",   # branded state dir  e.g. .blackstraw-adk/
        ".claude/",        # Claude settings + skills
        ".mcp.json",       # MCP server config
        "src/generated/",  # Claude-generated code
        ".databricks/",    # Databricks CLI cache
        ".env",
        "__pycache__/",
        "*.pyc",
    ]
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    new_rules = [r for r in rules if r not in existing]
    if new_rules:
        with gi.open("a", encoding="utf-8") as f:
            f.write("\n# Enterprise ADK\n" + "\n".join(new_rules) + "\n")


def _write_generated_readme(root: Path) -> None:
    readme = root / "src" / "generated" / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Generated Code\n\n"
            "This directory is managed by Claude Code.\n"
            "All AI-generated code is placed here automatically.\n\n"
            "> Do not manually edit files in this directory.\n",
            encoding="utf-8",
        )


def _write_starter_template(root: Path, enterprise_name: str) -> None:
    tmpl = root / "instruction-templates" / "default.md"
    if not tmpl.exists():
        tmpl.write_text(
            f"# Project Instructions\n\n"
            f"This project uses Databricks on the Lakehouse platform.\n"
            f"Enterprise: **{enterprise_name}**\n\n"
            f"## Code Generation Rules\n"
            f"- ALL generated code MUST go into `src/generated/`\n"
            f"- Never write generated files outside `src/generated/`\n\n"
            f"## Active Skills\n"
            f"- **Databricks skills**: all skills from ai-dev-kit\n"
            f"- **enterprise-naming-convention**: follow naming standards for all assets\n"
            f"- **enterprise-dynamic-modeling**: config-driven transformation patterns\n\n"
            f"## Context\n"
            f"- Catalog: `<set your catalog>`\n"
            f"- Environment: `dev | staging | prod`\n"
            f"- Team: `<set your team>`\n",
            encoding="utf-8",
        )


def _write_metadata(root: Path, state_dir: str, enterprise_name: str, workspace_url: str) -> None:
    meta_path = root / state_dir / "metadata.json"
    now = datetime.now(timezone.utc).isoformat()
    metadata: dict = {
        "enterprise": enterprise_name,
        "workspace_url": workspace_url,
        "project_root": str(root),
        "created_at": now,
    }
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            existing.update({k: v for k, v in metadata.items() if k != "created_at"})
            metadata = existing
        except (json.JSONDecodeError, OSError):
            pass
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
