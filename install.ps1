# Enterprise AI Dev Kit — Windows Installer (PowerShell)
# Usage: .\install.ps1
#        .\install.ps1 C:\path\to\project
#
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [string]$ProjectDir = ""
)

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   Enterprise AI Dev Kit — Installer      ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Python check ──────────────────────────────────────────────────────────────
$Python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
        if ($ver) {
            $parts = $ver -split " "
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
                $Python = $cmd
                break
            }
        }
    } catch {}
}

if (-not $Python) {
    Write-Host "ERROR: Python 3.10+ required."
    Write-Host "Install from: https://www.python.org/downloads/"
    exit 1
}

$pyVer = & $Python --version
Write-Host "✓ $pyVer"

# ── Install the package ───────────────────────────────────────────────────────
$uvAvailable = $null -ne (Get-Command uv -ErrorAction SilentlyContinue)

if ($uvAvailable) {
    Write-Host "Installing via uv…"
    uv tool install $RepoDir --force 2>$null
    if ($LASTEXITCODE -ne 0) {
        uv pip install -e $RepoDir
    }
} else {
    Write-Host "Installing via pip…"
    & $Python -m pip install -e $RepoDir --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed."
        exit 1
    }
}

Write-Host ""
Write-Host "✓ enterprise-adk installed"
Write-Host ""

# ── Ensure Scripts directory is in PATH ──────────────────────────────────────
$scriptsDir = & $Python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$scriptsDir*") {
    [System.Environment]::SetEnvironmentVariable(
        "PATH",
        "$userPath;$scriptsDir",
        "User"
    )
    Write-Host "✓ Added $scriptsDir to your user PATH"
    Write-Host "  (Restart your terminal for this to take effect)"
    $env:PATH += ";$scriptsDir"
}

# ── Create branded wrapper ────────────────────────────────────────────────────
$EntName = & $Python -c "
from enterprise_adk.config.loader import load_config
print(load_config().enterprise.cli_command)
" 2>$null
if (-not $EntName) { $EntName = "enterprise" }

$AdkCmd = "enterprise-adk"
if ($EntName -ne "enterprise") {
    $scriptsDir = & $Python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
    $wrapper    = Join-Path $scriptsDir "$EntName-adk.bat"
    "@echo off`nenterprise-adk %*`n" | Set-Content $wrapper -Encoding ASCII
    Write-Host "✓ $EntName-adk wrapper created at $wrapper"
    $AdkCmd = "$EntName-adk"
}

Write-Host ""

# ── Run init if a project path was given ─────────────────────────────────────
if ($ProjectDir) {
    Write-Host "Running: $AdkCmd init $ProjectDir"
    & $AdkCmd init $ProjectDir
} else {
    Write-Host "Next step:"
    Write-Host "  $AdkCmd init                       # init current directory"
    Write-Host "  $AdkCmd init C:\path\to\proj       # init specific directory"
}
