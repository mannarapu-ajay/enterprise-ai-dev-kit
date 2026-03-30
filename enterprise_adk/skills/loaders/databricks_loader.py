"""Load Databricks skills from the cloned ai-dev-kit repository."""

from __future__ import annotations

import shutil
from pathlib import Path

from enterprise_adk.setup import REPO_DIR

DATABRICKS_SKILLS_SRC = REPO_DIR / "databricks-skills"


class DatabricksSkillLoader:
    """Copy skills from the locally cloned ai-dev-kit repo into the project."""

    def load(self, skills_dir: Path, *, force: bool = False) -> list[str]:
        """Copy all Databricks skills into skills_dir. Returns list of skill names."""
        if not DATABRICKS_SKILLS_SRC.exists():
            return []

        skill_dirs = [
            d for d in DATABRICKS_SKILLS_SRC.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]

        installed: list[str] = []
        for src in sorted(skill_dirs):
            dest = skills_dir / src.name
            if dest.exists():
                if not force:
                    installed.append(src.name)
                    continue
                shutil.rmtree(dest)
            shutil.copytree(str(src), str(dest))
            installed.append(src.name)

        return installed
