# Enterprise AI Dev Kit

A turnkey CLI that wraps [Databricks AI Dev Kit](https://github.com/databricks-solutions/ai-dev-kit) and layers on enterprise-specific skills for Claude Code.
Data engineers get a fully configured Databricks + Claude workspace in one command.

---

## How it works

```
enterprise-ai-dev-kit/
├── enterprise_adk/
│   └── enterprise_config.yaml   ← enterprise team edits this once
├── enterprise_skills/            ← bundled enterprise skills
├── install.sh                    ← Mac / Linux installer
└── install.ps1                   ← Windows installer
```

The enterprise team forks this repo, edits `enterprise_config.yaml` once, and distributes it.
Data engineers install it and get a branded CLI (`blackstraw-adk`, `acme-adk`, etc.) ready to use.

---

## For the Enterprise Team

### 1. Configure

Edit `enterprise_adk/enterprise_config.yaml`:

```yaml
enterprise:
  name: blackstraw            # your org slug
  display_name: Blackstraw    # shown in banners
  cli_command: blackstraw     # CLI becomes "blackstraw-adk"

ai_dev_kit:
  repo: https://github.com/databricks-solutions/ai-dev-kit.git
  version: v0.1.5             # pin the ai-dev-kit version

skills:
  source: bundled             # bundled | local | git
```

**Skills source options:**

| Option | Config |
|--------|--------|
| Bundled (default) | `source: bundled` |
| Local path | `source: local` / `path: ../enterprise-skills` |
| Git repo | `source: git` / `repo: https://github.com/org/skills` / `ref: v2.0.0` |

### 2. Add enterprise skills

Drop skill folders into `enterprise_skills/`. Each skill needs a `SKILL.md`:

```
enterprise_skills/
├── enterprise-naming-convention/
│   └── SKILL.md
└── enterprise-dynamic-modeling/
    └── SKILL.md
```

### 3. Distribute

```bash
# Publish to your internal PyPI or share the repo URL
pip install git+https://github.com/your-org/enterprise-ai-dev-kit
```

---

## For Data Engineers

### Install

**Mac / Linux:**
```bash
sh install.sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

**Or directly with pip:**
```bash
pip install git+https://github.com/your-org/enterprise-ai-dev-kit
```

After install, the branded CLI is immediately available:
```bash
blackstraw-adk --help
```

---

### Initialize a project

```bash
# Init in current directory
blackstraw-adk init

# Init in a specific path
blackstraw-adk init /path/to/my-project
```

The `init` command runs 4 steps:

| Step | What happens |
|------|-------------|
| **1. Prerequisites** | Checks and installs `git`, `uv`, Databricks CLI |
| **2. Authentication** | Databricks OAuth login + MCP server setup (project-level) |
| **3. Skills** | Installs all Databricks skills + enterprise skills into `.claude/skills/` |
| **4. Workspace** | Creates project structure, `version.lock`, `.gitignore` |

**Workspace created:**

```
my-project/
├── .blackstraw-adk/          ← state: version.lock, metadata, skill manifest
├── .claude/
│   └── skills/
│       ├── databricks-jobs/
│       ├── databricks-genie/
│       ├── enterprise-naming-convention/
│       └── enterprise-dynamic-modeling/
├── .mcp.json                 ← MCP server config (project-level)
├── instruction-templates/
│   └── default.md            ← starter instructions for Claude
└── src/
    └── generated/            ← all Claude-generated code goes here
```

> `.blackstraw-adk/`, `.claude/`, `.mcp.json`, and `src/generated/` are added to `.gitignore` automatically.

---

### Update skills

```bash
# Update everything
blackstraw-adk update

# Update only Databricks skills (checks GitHub for latest version, asks to confirm)
blackstraw-adk update databricks

# Update only enterprise skills
blackstraw-adk update blackstraw
```

The Databricks update shows you current vs latest before doing anything:

```
  Installed version  : v0.1.5
  Latest version     : v0.1.6
  Upgrade? [Y/n]:
```

---

## Version management

Every project gets a `.blackstraw-adk/version.lock`:

```json
{
  "enterprise_adk": "0.1.0",
  "ai_dev_kit": "v0.1.5",
  "enterprise_skills": "bundled",
  "databricks_workspace": "https://xxx.azuredatabricks.net",
  "installed_at": "2026-03-26T10:00:00+00:00"
}
```

---

## Requirements

- Python 3.10+
- `git`
- `uv` (auto-installed if missing)
- Databricks CLI (auto-installed if missing)
- Claude Code

---

## Platform support

| Platform | Installer | CLI |
|----------|-----------|-----|
| macOS | `sh install.sh` | `blackstraw-adk` |
| Linux | `sh install.sh` | `blackstraw-adk` |
| Windows | `install.ps1` | `blackstraw-adk` |
