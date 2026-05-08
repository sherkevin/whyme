# =============================================================================
# Mydow / PRD10 — Postgres logical backup (custom format) — Windows.
#
# Produces ``${BackupDir}\postgres\<stamp>_<db>.dump`` with a sibling
# ``.sha256`` file, then prunes anything older than RetentionDays.
#
# Required:
#   $env:DATABASE_URL or -DatabaseUrl param  (postgresql[+asyncpg]://user:pass@host:port/db)
# Optional:
#   $env:BACKUP_DIR | -BackupDir
#   $env:AGENTOS_BACKUP_RETENTION_DAYS | -RetentionDays  (default 14)
#   $env:AGENTOS_BACKUP_S3_BUCKET | -S3Bucket
#   $env:AGENTOS_BACKUP_S3_PREFIX | -S3Prefix             (default mydow/postgres)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\backup\backup_postgres.ps1
#
# Exit codes mirror the bash sibling:
#   0 — success
#   1 — bad config / missing tools
#   2 — pg_dump failed
#   3 — checksum / upload failed
# =============================================================================

[CmdletBinding()]
param(
    [string] $DatabaseUrl    = $env:DATABASE_URL,
    [string] $BackupDir      = $env:BACKUP_DIR,
    [int]    $RetentionDays  = $(if ($env:AGENTOS_BACKUP_RETENTION_DAYS) { [int]$env:AGENTOS_BACKUP_RETENTION_DAYS } else { 14 }),
    [string] $S3Bucket       = $env:AGENTOS_BACKUP_S3_BUCKET,
    [string] $S3Prefix       = $(if ($env:AGENTOS_BACKUP_S3_PREFIX) { $env:AGENTOS_BACKUP_S3_PREFIX } else { 'mydow/postgres' })
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $RepoRoot

if (-not $BackupDir) {
    $BackupDir = Join-Path $RepoRoot '.tmp\backups'
}

$Stamp     = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$PgDir     = Join-Path $BackupDir 'postgres'
$LogFile   = Join-Path $PgDir   '_backup.log'

if (-not (Test-Path $PgDir)) { New-Item -ItemType Directory -Path $PgDir -Force | Out-Null }

function Write-Log([string]$Message) {
    $ts = (Get-Date).ToUniversalTime().ToString('o')
    $line = "[${ts}] ${Message}"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

if (-not $DatabaseUrl) {
    $envFile = Join-Path $RepoRoot '.env'
    if (Test-Path $envFile) {
        $line = (Get-Content $envFile | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1)
        if ($line) { $DatabaseUrl = ($line -replace '^DATABASE_URL=', '').Trim('"').Trim() }
    }
}

if (-not $DatabaseUrl) {
    Write-Log 'ERROR: DATABASE_URL is not set'
    exit 1
}

# pg_dump only understands postgresql:// (not the SQLAlchemy +asyncpg/+psycopg variants).
$PgUrl = $DatabaseUrl `
    -replace '^postgresql\+asyncpg://', 'postgresql://' `
    -replace '^postgresql\+psycopg://',  'postgresql://'

# Bail early when we're pointed at SQLite — backup script is PG-only.
if ($PgUrl -match '^sqlite') {
    Write-Log "INFO: DATABASE_URL is sqlite, skipping pg_dump (use snapshot_uploads.* and copy the .db file directly)."
    exit 0
}

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    Write-Log 'ERROR: pg_dump is not on PATH (install postgresql-client / Postgres bin folder).'
    exit 1
}

# Extract DB name for the filename (last path segment, strip query).
$DbName = ($PgUrl -split '/')[-1] -split '\?', 2 | Select-Object -First 1
$DumpPath = Join-Path $PgDir "${Stamp}_${DbName}.dump"
$ShaPath  = "${DumpPath}.sha256"

Write-Log "Starting pg_dump of ${DbName} -> ${DumpPath}"

& $pgDump.Path `
    --format=custom `
    --compress=9 `
    --quote-all-identifiers `
    --no-acl `
    --no-owner `
    --dbname="$PgUrl" `
    --file="$DumpPath"

if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: pg_dump exited with $LASTEXITCODE"
    exit 2
}

# SHA-256 sidecar.
try {
    $hash = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash.ToLower()
    "$hash  $(Split-Path $DumpPath -Leaf)" | Set-Content -Path $ShaPath -Encoding ASCII
}
catch {
    Write-Log "WARN: could not compute SHA-256: $($_.Exception.Message)"
}

if ($S3Bucket) {
    $aws = Get-Command aws -ErrorAction SilentlyContinue
    if (-not $aws) {
        Write-Log 'ERROR: AGENTOS_BACKUP_S3_BUCKET set but aws CLI not on PATH.'
        exit 3
    }
    $key = "s3://${S3Bucket}/${S3Prefix}/$(Split-Path $DumpPath -Leaf)"
    Write-Log "Uploading to $key"
    & $aws.Path s3 cp $DumpPath $key
    if (Test-Path $ShaPath) {
        & $aws.Path s3 cp $ShaPath "s3://${S3Bucket}/${S3Prefix}/$(Split-Path $ShaPath -Leaf)"
    }
}

Write-Log "Pruning local dumps older than $RetentionDays days"
$cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
Get-ChildItem -Path $PgDir -File -Filter "*_${DbName}.dump*" |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Write-Log "Deleting $($_.FullName)"
        Remove-Item -Force -Path $_.FullName
    }

$size = (Get-Item $DumpPath).Length
Write-Log "Backup OK ($size bytes)"
