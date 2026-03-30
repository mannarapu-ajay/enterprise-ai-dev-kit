"""Pydantic v2 config models — mirrors enterprise_config.yaml structure."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class EnterpriseConfig(BaseModel):
    name: str = "enterprise"
    display_name: str = ""
    cli_command: str = ""       # defaults to name when empty

    @model_validator(mode="after")
    def _default_cli_command(self) -> "EnterpriseConfig":
        if not self.cli_command:
            self.cli_command = self.name
        return self

    @property
    def adk_binary(self) -> str:
        """e.g. 'blackstraw-adk'"""
        return f"{self.cli_command}-adk"


class AiDevKitConfig(BaseModel):
    repo: str = "https://github.com/databricks-solutions/ai-dev-kit.git"
    version: str = "main"       # branch name or tag: main, v0.1.5, v0.1.6


class SkillsConfig(BaseModel):
    source: Literal["bundled", "local", "git"] = "bundled"
    repo: str = ""
    ref: str = "main"
    path: str = ""


class AppConfig(BaseModel):
    enterprise: EnterpriseConfig = Field(default_factory=EnterpriseConfig)
    ai_dev_kit: AiDevKitConfig   = Field(default_factory=AiDevKitConfig)
    skills: Optional[SkillsConfig] = Field(default_factory=SkillsConfig)

    @property
    def adk_name(self) -> str:
        """Full branded CLI name, e.g. 'blackstraw-adk'."""
        return self.enterprise.adk_binary
