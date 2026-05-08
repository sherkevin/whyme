# =============================================================================
# Mydow / PRD10 — Postgres logical restore (Windows).
#
# Reads a dump produced by ``backup_postgres.ps1`` and applies it to
# the database in ``-Target`` / ``$env:DATABASE_URL``.
#
# Usage:
#   powershell scripts\backup\restore_postgres.ps1 .\.tmp\backups\postgres\20260506T...dump
#   powershell scripts\backup\restore_postgres.ps1 latest
#   powershell scripts\backup\restore_postgres.ps1 latest -Target postgresql://user:pass@host/db
#
# Safety:
#   * Refuses to run when -Target host contains "prod"/"production" unless -Force.
#   * Always uses --clean --if-exists.
#   * Verifies the SHA-256 sidecar when it exists.
# =============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $DumpArg,
    [string] $Target = $env:DATABASE_URL,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $RepoRoot
$BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $RepoRoot '.tmp\backups' }
$PgDir     = Join-Path $BackupDir 'postgres'

if ($DumpArg -eq 'latest') {
    $candidate = Get-ChildItem -Path $PgDir -Filter '*.dump' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        Write-Error "No dumps found under $PgDir"
    }
    $DumpPath = $candidate.FullName
}
else {
    $DumpPath = $DumpArg
}

if (-not (Test-Path $DumpPath)) {
    Write-Error "Dump not found: $DumpPath"
}

if (-not $Target) {
    Write-Error "Target / DATABASE_URL is required."
}

$PgUrl = $Target `
    -replace '^postgresql\+asyncpg://', 'postgresql://' `
    -replace '^postgresql\+psycopg://',  'postgresql://'

if ($PgUrl -match '(?i)prod|production' -and -not $Force) {
    Write-Error "Refusing to restore into production-looking host: $PgUrl. Pass -Force to override."
}

$ShaPath = "$DumpPath.sha256"
if (Test-Path $ShaPath) {
    $expected = (Get-Content $ShaPath -ErrorAction Stop | Select-Object -First 1).Split(' ')[0]
    $actual   = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash.ToLower()
    if ($expected.ToLower() -ne $actual) {
        Write-Error "SHA-256 mismatch: expected $expected, got $actual"
    }
    Write-Host "SHA-256 verified ($actual)"
}

$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
if (-not $pgRestore) {
    Write-Error 'pg_restore not on PATH'
}

Write-Host "Restoring $DumpPath into $PgUrl"

& $pgRestore.Path `
    --clean `
    --if-exists `
    --no-acl `
    --no-owner `
    --dbname="$PgUrl" `
    "$DumpPath"

if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_restore exited with $LASTEXITCODE"
}

Write-Host 'Restore complete.'
