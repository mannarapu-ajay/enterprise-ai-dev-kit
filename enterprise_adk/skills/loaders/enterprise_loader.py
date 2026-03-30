"""Load enterprise skills from bundled package, a local path, or a git repository."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

# Bundled enterprise skills ship alongside this package
_PKG_ROOT = Path(__file__).parent.parent.parent.parent
BUNDLED_SKILLS_SRC = _PKG_ROOT / "enterprise_skills"


class EnterpriseSkillLoader:
    """Load enterprise skills from one of three sources: bundled, local, or git."""

    def __init__(
        self,
        source: str = "bundled",
        path: str = "",
        repo: str = "",
        ref: str = "main",
    ) -> None:
        self.source = source
        self.path   = path
        self.repo   = repo
        self.ref    = ref

    def load(self, skills_dir: Path, *, force: bool = False) -> list[str]:
        """Install enterprise skills into skills_dir. Returns list of skill names."""
        if self.source == "local":
            return self._from_dir(Path(self.path), skills_dir, force)
        if self.source == "git":
            return self._from_git(skills_dir, force)
        # bundled (default)
        return self._from_dir(BUNDLED_SKILLS_SRC, skills_dir, force)

    # ── sources ──────────────────────────────────────────────────────────────

    def _from_dir(self, src: Path, skills_dir: Path, force: bool) -> list[str]:
        if not src.exists():
            return []
        skill_dirs = [d for d in src.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        installed: list[str] = []
        for skill_src in sorted(skill_dirs):
            dest = skills_dir / skill_src.name
            if dest.exists():
                if not force:
                    installed.append(skill_src.name)
                    continue
                shutil.rmtree(dest)
            shutil.copytree(str(skill_src), str(dest))
            installed.append(skill_src.name)
        return installed

    def _from_git(self, skills_dir: Path, force: bool) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", self.ref, self.repo, tmp],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return []
            src = Path(tmp) / self.path if self.path else Path(tmp)
            return self._from_dir(src, skills_dir, force)
