#!/usr/bin/env bash
# Enterprise AI Dev Kit — installer
# Usage: sh install.sh
#        sh install.sh /path/to/project
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${1:-}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Enterprise AI Dev Kit — Installer      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Python check ──────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ required."
    echo "Install via: https://github.com/pyenv/pyenv"
    exit 1
fi

echo "✓ Python: $($PYTHON --version)"

# ── Install the package ───────────────────────────────────────────────────────
if command -v uv &>/dev/null; then
    echo "Installing via uv…"
    uv tool install "$REPO_DIR" --force 2>/dev/null || uv pip install -e "$REPO_DIR"
else
    echo "Installing via pip…"
    "$PYTHON" -m pip install -e "$REPO_DIR" --quiet
fi

echo ""
echo "✓ enterprise-adk installed"

# ── Create branded wrapper ────────────────────────────────────────────────────
ENT_NAME=$("$PYTHON" -c "
from enterprise_adk.config.loader import load_config
print(load_config().enterprise.cli_command)
" 2>/dev/null || echo "enterprise")

if [ "$ENT_NAME" != "enterprise" ]; then
    WRAPPER_DIR="$HOME/.local/bin"
    mkdir -p "$WRAPPER_DIR"
    WRAPPER="$WRAPPER_DIR/${ENT_NAME}-adk"
    printf '#!/usr/bin/env sh\nexec enterprise-adk "$@"\n' > "$WRAPPER"
    chmod +x "$WRAPPER"
    echo "✓ ${ENT_NAME}-adk wrapper created at $WRAPPER"
    echo ""
    echo "  Add ~/.local/bin to PATH if not already there:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    ADK_CMD="${ENT_NAME}-adk"
else
    ADK_CMD="enterprise-adk"
fi

echo ""

# ── Run init if a project path was given ─────────────────────────────────────
if [ -n "$PROJECT_DIR" ]; then
    echo "Running: $ADK_CMD init $PROJECT_DIR"
    "$ADK_CMD" init "$PROJECT_DIR"
else
    echo "Next step:"
    echo "  $ADK_CMD init               # init current directory"
    echo "  $ADK_CMD init /path/to/proj # init specific directory"
fi
