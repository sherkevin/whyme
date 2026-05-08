# =============================================================================
# Mydow / PRD10 — Snapshot uploads directory (Windows).
# =============================================================================

[CmdletBinding()]
param(
    [string] $UploadsBase    = $env:PRD10_UPLOADS_BASE,
    [string] $BackupDir      = $env:BACKUP_DIR,
    [int]    $RetentionDays  = $(if ($env:AGENTOS_BACKUP_RETENTION_DAYS) { [int]$env:AGENTOS_BACKUP_RETENTION_DAYS } else { 14 }),
    [string] $S3Bucket       = $env:AGENTOS_BACKUP_S3_BUCKET,
    [string] $S3Prefix       = $(if ($env:AGENTOS_BACKUP_S3_PREFIX) { $env:AGENTOS_BACKUP_S3_PREFIX } else { 'mydow/uploads' })
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $RepoRoot

if (-not $UploadsBase) { $UploadsBase = Join-Path $RepoRoot 'data\uploads' }
if (-not $BackupDir)   { $BackupDir   = Join-Path $RepoRoot '.tmp\backups' }

if (-not (Test-Path $UploadsBase)) {
    Write-Host "Uploads dir does not exist: $UploadsBase — nothing to snapshot."
    exit 0
}

$UpDir = Join-Path $BackupDir 'uploads'
if (-not (Test-Path $UpDir)) { New-Item -ItemType Directory -Path $UpDir -Force | Out-Null }

$Stamp        = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$ArchivePath  = Join-Path $UpDir "${Stamp}_uploads.tar.gz"
$ShaPath      = "$ArchivePath.sha256"
$LogFile      = Join-Path $UpDir '_snapshot.log'

function Write-Log([string]$Message) {
    $ts = (Get-Date).ToUniversalTime().ToString('o')
    $line = "[${ts}] ${Message}"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

# Use the system tar (Windows 10+ ships bsdtar). Pass relative paths so we
# don't bake absolute paths into the archive.
$tar = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tar) {
    Write-Error 'tar not found on PATH (Windows 10+ ships bsdtar at C:\Windows\System32\tar.exe).'
}

$Parent = Split-Path -Parent $UploadsBase
$Leaf   = Split-Path -Leaf   $UploadsBase

Write-Log "Archiving $UploadsBase -> $ArchivePath"
Push-Location $Parent
try {
    & $tar.Path -czf $ArchivePath $Leaf
}
finally {
    Pop-Location
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "tar exited with $LASTEXITCODE"
}

try {
    $hash = (Get-FileHash -Path $ArchivePath -Algorithm SHA256).Hash.ToLower()
    "$hash  $(Split-Path $ArchivePath -Leaf)" | Set-Content -Path $ShaPath -Encoding ASCII
}
catch {
    Write-Log "WARN: SHA-256 failed: $($_.Exception.Message)"
}

if ($S3Bucket) {
    $aws = Get-Command aws -ErrorAction SilentlyContinue
    if ($aws) {
        $key = "s3://${S3Bucket}/${S3Prefix}/$(Split-Path $ArchivePath -Leaf)"
        Write-Log "Uploading to $key"
        & $aws.Path s3 cp $ArchivePath $key
        if (Test-Path $ShaPath) {
            & $aws.Path s3 cp $ShaPath "s3://${S3Bucket}/${S3Prefix}/$(Split-Path $ShaPath -Leaf)"
        }
    } else {
        Write-Log "WARN: AGENTOS_BACKUP_S3_BUCKET set but aws CLI not available."
    }
}

Write-Log "Pruning local snapshots older than $RetentionDays days"
$cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
Get-ChildItem -Path $UpDir -File -Filter '*_uploads.tar.gz*' |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Write-Log "Deleting $($_.FullName)"
        Remove-Item -Force -Path $_.FullName
    }

$size = (Get-Item $ArchivePath).Length
Write-Log "Snapshot OK ($size bytes)"
