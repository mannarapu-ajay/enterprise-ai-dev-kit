"""Skill manager — orchestrates Databricks + enterprise skill installation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from enterprise_adk.skills.loaders.databricks_loader import DatabricksSkillLoader
from enterprise_adk.skills.loaders.enterprise_loader import EnterpriseSkillLoader

if TYPE_CHECKING:
    from enterprise_adk.config.models import SkillsConfig

console = Console()

_MANIFEST = ".installed-skills"


class SkillManager:
    def __init__(self, skills_dir: Path, state_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.state_dir  = state_dir

    # ── public API ────────────────────────────────────────────────────────────

    def install_all(
        self,
        skills_cfg: Optional["SkillsConfig"] = None,
        *,
        force: bool = False,
    ) -> dict[str, list[str]]:
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        db  = self._install_databricks(force=force)
        ent = self._install_enterprise(skills_cfg, force=force)

        self._write_manifest(db + ent)
        return {"databricks": db, "enterprise": ent}

    def update_databricks(self) -> list[str]:
        updated  = self._install_databricks(force=True)
        existing = self._read_manifest()
        non_db   = [s for s in existing if not _is_databricks(s)]
        self._write_manifest(non_db + updated)
        return updated

    def update_enterprise(self, skills_cfg: Optional["SkillsConfig"] = None) -> list[str]:
        updated  = self._install_enterprise(skills_cfg, force=True)
        existing = self._read_manifest()
        db_only  = [s for s in existing if _is_databricks(s)]
        self._write_manifest(db_only + updated)
        return updated

    def list_installed(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return sorted(
            d.name for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    # ── internals ─────────────────────────────────────────────────────────────

    def _install_databricks(self, *, force: bool) -> list[str]:
        loader = DatabricksSkillLoader()

        from enterprise_adk.skills.loaders.databricks_loader import DATABRICKS_SKILLS_SRC
        if not DATABRICKS_SKILLS_SRC.exists():
            console.print("  [yellow]![/yellow] Databricks skills not found — MCP server not set up yet?")
            return []

        skill_dirs = [
            d for d in DATABRICKS_SKILLS_SRC.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]
        installed: list[str] = []
        with Progress(
            TextColumn("  [cyan]{task.description}[/cyan]"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            transient=True,
            console=console,
        ) as prog:
            t = prog.add_task("Databricks skills", total=len(skill_dirs))
            for src in sorted(skill_dirs):
                import shutil as _shutil
                dest = self.skills_dir / src.name
                if dest.exists():
                    if force:
                        _shutil.rmtree(dest)
                    else:
                        installed.append(src.name)
                        prog.advance(t)
                        continue
                _shutil.copytree(str(src), str(dest))
                installed.append(src.name)
                prog.advance(t)
        return installed

    def _install_enterprise(
        self,
        skills_cfg: Optional["SkillsConfig"],
        *,
        force: bool,
    ) -> list[str]:
        if skills_cfg:
            loader = EnterpriseSkillLoader(
                source=skills_cfg.source,
                path=skills_cfg.path,
                repo=skills_cfg.repo,
                ref=skills_cfg.ref,
            )
        else:
            loader = EnterpriseSkillLoader()
        return loader.load(self.skills_dir, force=force)

    def _write_manifest(self, skill_names: list[str]) -> None:
        lines = [f"{self.skills_dir}|{name}" for name in sorted(set(skill_names))]
        (self.state_dir / _MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _read_manifest(self) -> list[str]:
        path = self.state_dir / _MANIFEST
        if not path.exists():
            return []
        names: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split("|")
            if len(parts) == 2:
                names.append(parts[1])
        return names


def _is_databricks(name: str) -> bool:
    return name.startswith("databricks") or name.startswith("spark")
