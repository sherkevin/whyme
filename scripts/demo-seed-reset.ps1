# PRD10 §10.7 — Demo seed periodic reset (Windows Task Scheduler).
#
# Re-seeds the demo@mydow.example account every 24h so investors / new
# evaluators always land on a clean dataset (6 folders / 20 documents /
# 30 cards / 5 tasks / 5 notifications / 3 ai conversations / 18 ai
# messages / 5 skills / 10 search documents / 6 insights). This is
# essential for continuous demo reliability — without it, the demo path
# accumulates random user input from prior sessions and breaks the
# carefully tuned "first 30 seconds" pitch.
#
# Schedule (Windows Task Scheduler example):
#
#   $action  = New-ScheduledTaskAction -Execute "pwsh.exe" `
#              -Argument "-NoProfile -ExecutionPolicy Bypass -File `"D:\Codes\whyme\scripts\demo-seed-reset.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 4am
#   Register-ScheduledTask -TaskName "MydowDemoSeedReset" `
#                          -Action $action -Trigger $trigger `
#                          -Description "Reset Mydow demo account every 24h"
#
# To run once locally:  pwsh -File scripts/demo-seed-reset.ps1
#
# Environment overrides:
#
#   $env:DEMO_DATABASE_URL    SQLAlchemy URL of the demo DB.
#   $env:DEMO_EMAIL           Demo account email (default demo@mydow.example).
#   $env:DEMO_PASSWORD        Demo account password (default demo123).
#   $env:DEMO_PROJECT_ROOT    Repo root (default the repo housing this script).

[CmdletBinding()]
param(
    [string]$DatabaseUrl  = $env:DEMO_DATABASE_URL,
    [string]$DemoEmail    = $env:DEMO_EMAIL,
    [string]$DemoPassword = $env:DEMO_PASSWORD,
    [string]$ProjectRoot  = $env:DEMO_PROJECT_ROOT
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")
}
if (-not (Test-Path $ProjectRoot)) {
    Write-Error "Project root not found: $ProjectRoot"
    exit 1
}

if (-not $DatabaseUrl) {
    $DatabaseUrl = "sqlite+aiosqlite:///$ProjectRoot\.tmp\demo.db"
}
if (-not $DemoEmail)    { $DemoEmail    = "demo@mydow.example" }
if (-not $DemoPassword) { $DemoPassword = "demo123" }

$logDir = Join-Path $ProjectRoot ".tmp"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$logFile = Join-Path $logDir "demo-seed-reset.log"

$start = Get-Date
"[${start}] Reset start (db=$DatabaseUrl email=$DemoEmail)" | Add-Content -Path $logFile -Encoding UTF8

$env:DATABASE_URL = $DatabaseUrl
$env:PYTHONPATH   = "$ProjectRoot\src"
$env:AGENTOS_DEMO_MODE = "on"

Push-Location $ProjectRoot
try {
    # PowerShell 5.1 (powershell.exe) treats any stderr line as
    # NativeCommandError, so `python --reset` returning success but
    # printing a "WARNING:" line over stderr would crash the script.
    # `*>&1` merges all streams (stdout + stderr + warnings + verbose +
    # debug + information) into one pipeline so we capture the full
    # output without tripping the error trap.
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = python "scripts\seed_prd10.py" `
        --email $DemoEmail `
        --password $DemoPassword `
        --reset *>&1
    $exit = $LASTEXITCODE
    $ErrorActionPreference = $prevPref
    foreach ($line in $output) { "$line" | Add-Content -Path $logFile -Encoding UTF8 }
    if ($exit -ne 0) {
        "[$(Get-Date)] Reset FAILED with exit code $exit" | Add-Content -Path $logFile -Encoding UTF8
        exit $exit
    }
    "[$(Get-Date)] Reset OK ($([int]((Get-Date) - $start).TotalSeconds)s)" | Add-Content -Path $logFile -Encoding UTF8
} finally {
    Pop-Location
}

exit 0
