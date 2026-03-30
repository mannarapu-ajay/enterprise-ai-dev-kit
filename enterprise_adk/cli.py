"""Enterprise ADK — dynamic CLI.

The CLI name comes from enterprise_adk/enterprise_config.yaml:

    enterprise:
      name: blackstraw
      cli_command: blackstraw   # → install.sh creates "blackstraw-adk" wrapper

Commands:
    <name>-adk init [PATH]
    <name>-adk update
    <name>-adk update databricks
    <name>-adk update <enterprise-name>
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from enterprise_adk import __version__
from enterprise_adk.config.loader import load_config

# ── questionary colour theme ──────────────────────────────────────────────────
_Q_STYLE = questionary.Style([
    ("question",    "bold fg:ansibrightcyan"),
    ("answer",      "bold fg:ansibrightgreen"),
    ("pointer",     "bold fg:ansibrightcyan"),
    ("highlighted", "bold fg:ansibrightcyan"),
    ("selected",    "bold fg:ansibrightgreen"),
    ("instruction", "fg:ansiyellow"),
    ("separator",   "fg:ansibrightblack"),
])

# Bootstrap: read the package config once at import time.
_cfg      = load_config()
_ADK_NAME = _cfg.adk_name
_ENT_NAME = _cfg.enterprise.cli_command
_ENT_DISP = _cfg.enterprise.display_name or _cfg.enterprise.name.capitalize()

console = Console()

_CLAUDE_DIR = ".claude"
_STATE_DIR  = f".{_ADK_NAME}"
_PATH_HELP  = "Project directory."

app = typer.Typer(
    name=_ADK_NAME,
    help=(
        f"[bold]{_ADK_NAME}[/bold] — Databricks AI Dev Kit + Enterprise Skills for Claude Code.\n\n"
        f"Enterprise: [cyan]{_ENT_DISP}[/cyan]"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

update_app = typer.Typer(
    help="Update Databricks skills or enterprise skills.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)
app.add_typer(update_app, name="update")


@app.command()
def init(
    path: Optional[Path] = typer.Argument(
        None,
        help="Project root directory. Prompted interactively when omitted.",
    ),
) -> None:
    """Interactive setup: project → prereqs → workspace → auth → MCP + skills → workspace lock."""
    from enterprise_adk.installer import auth, mcp, workspace
    from enterprise_adk.installer.prereqs import check_and_fix
    from enterprise_adk.skills.manager import SkillManager
    from enterprise_adk.version.manager import VersionManager
    from enterprise_adk import certs

    cfg = load_config()
    _banner(cfg)

    # ── Step 1: Project directory ─────────────────────────────────────────────
    _step(1, 7, "Project Directory")
    project_root = _resolve_path(path)
    state_dir    = project_root / _STATE_DIR
    skills_dir   = project_root / _CLAUDE_DIR / "skills"

    # ── Step 2: Prerequisites ─────────────────────────────────────────────────
    _step(2, 7, "Prerequisites")
    if not check_and_fix():
        console.print("\n  [red]Fix the above issues and run init again.[/red]")
        raise typer.Exit(1)

    # ── Step 3: Workspace & profile selection + OAuth initiation ──────────────
    _step(3, 7, "Databricks Workspace & Profile")
    workspace_url, profile = _select_workspace_and_login(auth)

    # ── Step 4: Authentication confirmation + CA certs ────────────────────────
    _step(4, 7, "Authentication")
    _confirm_auth_and_certs(certs, workspace_url, profile)

    # ── Step 5: Compute configuration ─────────────────────────────────────────
    _step(5, 7, "Compute Configuration")
    compute = _select_compute(auth, profile)

    # ── Step 6: MCP server + skills ───────────────────────────────────────────
    _step(6, 7, "MCP Server + Skills")
    _run_mcp_step(mcp, project_root, profile, version=cfg.ai_dev_kit.version)

    mgr    = SkillManager(skills_dir, state_dir)
    result = mgr.install_all(cfg.skills)
    console.print(
        f"  [green]✓[/green] {len(result['databricks'])} Databricks skill(s)"
        f"  +  {len(result['enterprise'])} enterprise skill(s)"
    )

    # ── Step 7: Workspace + version lock ──────────────────────────────────────
    _step(7, 7, "Workspace + Version Lock")
    workspace.create(
        project_root,
        enterprise_name=cfg.enterprise.name,
        workspace_url=workspace_url,
        compute=compute,
    )
    console.print("  [green]✓[/green] src/generated/ , instruction-templates/ , .enterprise-adk/")

    vm = VersionManager(state_dir)
    vm.stamp_install(
        enterprise_adk=__version__,
        ai_dev_kit=cfg.ai_dev_kit.version,
        enterprise_skills=cfg.skills.ref if cfg.skills else "bundled",
        workspace_url=workspace_url,
        compute=compute,
    )
    console.print("  [green]✓[/green] version.lock written")

    _print_summary(project_root, skills_dir, cfg, workspace_url, vm.read())


@update_app.callback(invoke_without_command=True)
def update_all(
    ctx: typer.Context,
    path: Optional[Path] = typer.Option(None, "--path", "-p", help=_PATH_HELP),
) -> None:
    """Update both Databricks and enterprise skills."""
    if ctx.invoked_subcommand is None:
        _do_update_databricks(path)
        _do_update_enterprise(path)


@update_app.command("databricks")
def update_databricks(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help=_PATH_HELP),
) -> None:
    """Show current vs latest ai-dev-kit, confirm, then refresh Databricks skills."""
    _do_update_databricks(path)


def _update_enterprise_cmd(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help=_PATH_HELP),
) -> None:
    """Update enterprise skills from the configured source."""
    _do_update_enterprise(path)

update_app.command(_ENT_NAME)(_update_enterprise_cmd)


# ─── update implementations ──────────────────────────────────────────────────

def _do_update_databricks(path: Optional[Path]) -> None:
    from enterprise_adk.installer.mcp import update as update_mcp_repo
    from enterprise_adk.skills.manager import SkillManager
    from enterprise_adk.version.manager import VersionManager, compare_versions, fetch_latest_ai_dev_kit_tag

    cfg                                  = load_config()
    project_root, state_dir, skills_dir  = _resolve_project(path)
    vm                                   = VersionManager(state_dir)

    console.print()
    console.print(Panel.fit(
        f"[bold]{_ADK_NAME} — Update Databricks[/bold]\n[dim]{project_root}[/dim]",
        border_style="cyan",
    ))

    current = vm.get("ai_dev_kit", cfg.ai_dev_kit.version)
    console.print(f"\n  Configured version : [yellow]{cfg.ai_dev_kit.version}[/yellow]")
    console.print(f"  Installed version  : [yellow]{current}[/yellow]")
    console.print("  Checking GitHub for latest release…")

    latest = fetch_latest_ai_dev_kit_tag() or current
    console.print(f"  Latest version     : [green]{latest}[/green]")

    if current != "unknown" and not compare_versions(current, latest):
        console.print("  [green]✓[/green] Already up to date")
    else:
        if not Confirm.ask(
            f"  [bold]Upgrade ai-dev-kit {current} → {latest}?[/bold]",
            default=True,
            console=console,
        ):
            raise typer.Exit(0)
        console.print("\n  [bold]Pulling latest ai-dev-kit…[/bold]")
        try:
            new_ver = update_mcp_repo(latest)
            console.print(f"  [green]✓[/green] ai-dev-kit updated to {new_ver or latest}")
        except Exception as exc:
            console.print(f"  [red]✗[/red] Repo update failed: {exc}")

    console.print("\n  [bold]Refreshing Databricks skills…[/bold]")
    updated = SkillManager(skills_dir, state_dir).update_databricks()
    console.print(f"  [green]✓[/green] {len(updated)} Databricks skill(s) refreshed")

    vm.update_field(ai_dev_kit=latest)
    console.print("\n[green]Done.[/green]\n")


def _do_update_enterprise(path: Optional[Path]) -> None:
    from enterprise_adk.skills.manager import SkillManager
    from enterprise_adk.version.manager import VersionManager

    cfg                                  = load_config()
    project_root, state_dir, skills_dir  = _resolve_project(path)
    vm                                   = VersionManager(state_dir)

    console.print()
    console.print(Panel.fit(
        f"[bold]{_ADK_NAME} — Update {_ENT_DISP} Skills[/bold]\n[dim]{project_root}[/dim]",
        border_style="cyan",
    ))

    console.print("\n  [bold]Refreshing enterprise skills…[/bold]")
    updated = SkillManager(skills_dir, state_dir).update_enterprise(cfg.skills)
    console.print(f"  [green]✓[/green] {len(updated)} enterprise skill(s) refreshed")

    vm.update_field(enterprise_skills=cfg.skills.ref if cfg.skills else "bundled")
    console.print("\n[green]Done.[/green]\n")


# ─── init step helpers ────────────────────────────────────────────────────────

def _banner(cfg) -> None:
    console.print()
    console.print(Panel(
        Text.assemble(
            (cfg.adk_name, "bold white"),
            (f"  v{__version__}", "dim"),
            "\n",
            (f"{_ENT_DISP} — Enterprise AI Dev Kit", "dim"),
        ),
        border_style="cyan",
        padding=(0, 2),
    ))


def _step(n: int, total: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]Step {n} of {total}  —  {title}[/bold cyan]", style="cyan"))
    console.print()


def _resolve_path(path: Optional[Path]) -> Path:
    if path:
        project_root = path.resolve()
        console.print(f"  Project dir : [cyan]{project_root}[/cyan]")
    else:
        raw = Prompt.ask(
            "  [bold]Project directory[/bold]",
            default=str(Path.cwd()),
            console=console,
        )
        project_root = Path(raw).expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    return project_root


def _select_workspace_and_login(auth) -> tuple[str, str]:
    """Step 3: Domain/workspace selection, profile selection, and OAuth initiation."""
    workspace_url = ""

    # Domain + URL from edp_info.yml
    workspaces = _read_edp_workspaces()
    if workspaces:
        domain_name = questionary.select(
            "Choose domain / workspace:",
            choices=[ws["name"] for ws in workspaces],
            style=_Q_STYLE,
        ).ask()

        if domain_name:
            chosen_ws = next(ws for ws in workspaces if ws["name"] == domain_name)
            urls: dict[str, str] = chosen_ws.get("url", {})

            available_envs = [env for env in ("dev", "qa", "prod") if urls.get(env)]
            if len(available_envs) > 1:
                env_name = questionary.select(
                    "Authenticate against which environment?",
                    choices=available_envs,
                    default="dev" if "dev" in available_envs else available_envs[0],
                    style=_Q_STYLE,
                ).ask()
                workspace_url = urls.get(env_name or "dev", "")
            elif available_envs:
                workspace_url = urls[available_envs[0]]
                console.print(f"  [dim]→ {workspace_url}[/dim]")

    if not workspace_url:
        workspace_url = Prompt.ask(
            "  [bold]Databricks workspace URL[/bold]",
            default=auth.workspace_url_from_profile() or "",
            console=console,
        ).rstrip("/")

    console.print()

    # Profile selection from ~/.databrickscfg
    known_profiles = auth.available_profiles()
    _NEW_PROFILE   = "[ Create new profile ]"

    if known_profiles:
        profile_choice = questionary.select(
            "Choose Databricks profile:",
            choices=known_profiles + [_NEW_PROFILE],
            default=known_profiles[0],
            style=_Q_STYLE,
        ).ask()
        if profile_choice == _NEW_PROFILE or profile_choice is None:
            profile = Prompt.ask(
                "  [bold]New profile name[/bold]",
                default="DEFAULT",
                console=console,
            )
        else:
            profile = profile_choice
    else:
        profile = Prompt.ask(
            "  [bold]Config profile name[/bold]",
            default="DEFAULT",
            console=console,
        )

    # Initiate OAuth login if not already authenticated
    if workspace_url:
        console.print()
        if not _probe_auth(profile):
            console.print("  [yellow]![/yellow] Not authenticated — opening browser for OAuth login…")
            auth.oauth_login(workspace_url, profile=profile)
    else:
        console.print("  [dim]No workspace URL — skipping auth[/dim]")

    return workspace_url, profile


def _select_compute(auth, profile: str) -> dict:
    """Step 5: Choose compute type and configure cluster details."""
    _COMPUTE_ALL_PURPOSE = "All Purpose Compute"
    _COMPUTE_SERVERLESS  = "Serverless"
    _COMPUTE_JOB_CLUSTER = "Job Cluster"

    choice = questionary.select(
        "What compute will you use for asset bundles?",
        choices=[_COMPUTE_ALL_PURPOSE, _COMPUTE_SERVERLESS, _COMPUTE_JOB_CLUSTER],
        style=_Q_STYLE,
    ).ask()

    if choice == _COMPUTE_ALL_PURPOSE:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
            prog.add_task("  Fetching clusters from workspace…", total=None)
            clusters = auth.list_clusters(profile)
        if not clusters:
            console.print("  [yellow]![/yellow] No clusters found — enter cluster ID manually.")
            cluster_id = Prompt.ask(
                "  [bold]Cluster ID[/bold]", default="", console=console
            ).strip()
            return {"type": "all_purpose", "cluster_id": cluster_id, "cluster_name": ""}

        cluster_labels = [
            f"{c['name']}  [{c['state']}]  ({c['id']})" for c in clusters
        ]
        selected_label = questionary.select(
            "Choose a cluster:",
            choices=cluster_labels,
            style=_Q_STYLE,
        ).ask()

        if selected_label:
            idx     = cluster_labels.index(selected_label)
            cluster = clusters[idx]
            console.print(f"  [green]✓[/green] Cluster: {cluster['name']}  ({cluster['id']})")
            return {"type": "all_purpose", "cluster_id": cluster["id"], "cluster_name": cluster["name"]}
        return {"type": "all_purpose", "cluster_id": "", "cluster_name": ""}

    if choice == _COMPUTE_SERVERLESS:
        console.print("  [green]✓[/green] Serverless compute selected")
        return {"type": "serverless"}

    # Job Cluster — prompt with defaults, allow overwrite
    console.print("  [dim]Configure job cluster spec (press Enter to accept defaults):[/dim]")
    console.print()
    spark_version = Prompt.ask(
        "  [bold]Spark version[/bold]",
        default="15.4.x-scala2.12",
        console=console,
    ).strip()
    node_type_id = Prompt.ask(
        "  [bold]Node type ID[/bold]",
        default="Standard_DS3_v2",
        console=console,
    ).strip()
    num_workers_raw = Prompt.ask(
        "  [bold]Number of workers[/bold]",
        default="2",
        console=console,
    ).strip()
    try:
        num_workers = int(num_workers_raw)
    except ValueError:
        num_workers = 2

    console.print(
        f"  [green]✓[/green] Job cluster: {node_type_id}, "
        f"{spark_version}, {num_workers} workers"
    )
    return {
        "type": "job_cluster",
        "spark_version": spark_version,
        "node_type_id": node_type_id,
        "num_workers": num_workers,
    }


def _confirm_auth_and_certs(certs, workspace_url: str, profile: str) -> None:
    """Step 4: Confirm authentication result and configure CA certs."""
    if workspace_url:
        email = _probe_auth(profile)
        if email:
            console.print(f"  [green]✓[/green] Authenticated as {email}")
        else:
            console.print("  [yellow]![/yellow] Auth could not be confirmed — re-authenticate later:")
            console.print(f"  [dim]    databricks auth login --host {workspace_url}[/dim]")
        console.print()

    console.print("  [bold]Configuring CA certificates…[/bold]")
    if certs.already_configured():
        console.print("  [green]✓[/green] NODE_EXTRA_CA_CERTS already set")
    else:
        certs.setup_ca_certs()


def _run_mcp_step(mcp, project_root: Path, profile: str, version: str) -> None:
    console.print("  [bold]Setting up Databricks MCP server…[/bold]")
    try:
        mcp_path, settings_path = mcp.setup(project_root, profile=profile, version=version)
        console.print("  [green]✓[/green] MCP server ready")
        console.print(f"  [green]✓[/green] {mcp_path.relative_to(project_root)}")
        console.print(f"  [green]✓[/green] {settings_path.relative_to(project_root)}")
    except Exception as exc:
        console.print(f"  [red]✗[/red] MCP setup failed: {exc}")
        raise typer.Exit(1) from exc
    console.print()
    console.print("  [bold]Installing skills…[/bold]")


def _resolve_project(path: Optional[Path]) -> tuple[Path, Path, Path]:
    project_root = (path or Path.cwd()).resolve()
    state_dir    = project_root / _STATE_DIR
    skills_dir   = project_root / _CLAUDE_DIR / "skills"
    if not skills_dir.exists():
        console.print(
            f"[red]No .claude/skills found in {project_root}. "
            f"Run '{_ADK_NAME} init' first.[/red]"
        )
        raise typer.Exit(1)
    return project_root, state_dir, skills_dir


def _format_compute(compute: dict) -> str:
    t = compute.get("type", "")
    if t == "all_purpose":
        name = compute.get("cluster_name") or compute.get("cluster_id", "")
        cid  = compute.get("cluster_id", "")
        return f"All Purpose — {name} ({cid})" if name != cid else f"All Purpose — {cid}"
    if t == "serverless":
        return "Serverless"
    if t == "job_cluster":
        return (
            f"Job Cluster — {compute.get('node_type_id', '')}, "
            f"{compute.get('num_workers', '')} workers"
        )
    return t or "not set"


def _print_summary(
    project_root: Path,
    skills_dir: Path,
    cfg,
    workspace_url: str,
    lock: dict,
) -> None:
    installed  = (
        sorted(d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
        if skills_dir.exists() else []
    )
    db_skills  = [s for s in installed if s.startswith("databricks") or s.startswith("spark")]
    ent_skills = [s for s in installed if s.startswith("enterprise")]

    compute_str = _format_compute(lock.get("compute") or {})

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("[dim]Project[/dim]",            str(project_root))
    t.add_row("[dim]Enterprise[/dim]",         _ENT_DISP)
    t.add_row("[dim]CLI[/dim]",                cfg.adk_name)
    t.add_row("[dim]Workspace[/dim]",          workspace_url or "[dim]not set[/dim]")
    t.add_row("[dim]Compute[/dim]",            compute_str)
    t.add_row("[dim]Databricks skills[/dim]",  f"{len(db_skills)} installed")
    t.add_row("[dim]Enterprise skills[/dim]",  ", ".join(ent_skills) or "none")
    t.add_row("[dim]ai-dev-kit version[/dim]", lock.get("ai_dev_kit", cfg.ai_dev_kit.version))
    t.add_row("[dim]MCP config[/dim]",         str(project_root / ".mcp.json"))

    console.print()
    console.print(Panel(t, title="[bold green]✓ Workspace Ready[/bold green]", border_style="green"))
    console.print()
    console.print(f"  Open Claude Code in [cyan]{project_root}[/cyan] — MCP + all skills are active.")
    console.print(f"  To update skills: [cyan]{cfg.adk_name} update[/cyan]")
    console.print()


# ─── shared utilities ─────────────────────────────────────────────────────────

def _probe_auth(profile: str) -> str | None:
    """Check Databricks auth for the given profile; return email or None."""
    result = subprocess.run(
        ["databricks", "current-user", "me", "--profile", profile],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout).get("userName") or None
        except Exception:
            return None
    return None


def _read_edp_workspaces() -> list[dict[str, Any]]:
    """Load workspace definitions from the bundled edp_info.yml."""
    import yaml
    edp_path = Path(__file__).parent / "edp_info.yml"
    if not edp_path.exists():
        return []
    try:
        with open(edp_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data.get("databricks", {}).get("workspaces", []) or []
    except Exception:
        return []


def main() -> None:
    _ensure_wrapper()
    app()


def _ensure_wrapper() -> None:
    """Auto-create the branded CLI wrapper on first run after pip install."""
    import platform as _platform
    if _ADK_NAME == "enterprise-adk":
        return
    if _platform.system() == "Windows":
        import sysconfig
        scripts_dir = Path(sysconfig.get_path("scripts"))
        wrapper     = scripts_dir / f"{_ADK_NAME}.bat"
        if not wrapper.exists():
            try:
                wrapper.write_text("@echo off\nenterprise-adk %*\n", encoding="utf-8")
            except OSError:
                pass
    else:
        wrapper = Path.home() / ".local" / "bin" / _ADK_NAME
        if not wrapper.exists():
            try:
                import stat
                wrapper.parent.mkdir(parents=True, exist_ok=True)
                wrapper.write_text(
                    '#!/usr/bin/env sh\nexec enterprise-adk "$@"\n',
                    encoding="utf-8",
                )
                wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass


if __name__ == "__main__":
    main()
