param(
    [switch]$NoOpen,
    [switch]$NoBuild,
    [switch]$NoSeed,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $Root ".env.docker.local"
$ComposeFile = Join-Path $Root "docker-compose.prd10.yml"
$FrontendUrl = "http://localhost:$Port/mydow/biz_v14/"
$HealthUrl = "http://localhost:$Port/health"

function Get-ProjectEnvValue {
    param([string]$Name)
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($processValue) { return $processValue }

    $sourceEnv = Join-Path $Root ".env"
    if (-not (Test-Path $sourceEnv)) { return "" }

    foreach ($line in Get-Content $sourceEnv) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$") {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return ""
}

function New-Secret {
    return ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))
}

function Get-DockerPostgresSettings {
    $user = Get-ProjectEnvValue "POSTGRES_USER"
    $password = Get-ProjectEnvValue "POSTGRES_PASSWORD"
    $database = Get-ProjectEnvValue "POSTGRES_DB"
    if (-not $user) { $user = "agentos" }
    if (-not $password) { $password = "agentos" }
    if (-not $database) { $database = "agentos_db" }
    return @{
        User = $user
        Password = $password
        Database = $database
    }
}

function Get-DatabaseUrlComponent {
    param([string]$Value)
    return [System.Uri]::EscapeDataString($Value)
}

function Get-DockerDefaultDatabaseUrl {
    $pg = Get-DockerPostgresSettings
    $user = Get-DatabaseUrlComponent $pg.User
    $password = Get-DatabaseUrlComponent $pg.Password
    $database = Get-DatabaseUrlComponent $pg.Database
    return "postgresql+asyncpg://$user`:$password@postgres:5432/$database"
}

function Get-EnvFileValue {
    param(
        [string[]]$Lines,
        [string]$Name
    )
    foreach ($line in $Lines) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$") {
            return $Matches[1].Trim()
        }
    }
    return ""
}

function Set-EnvFileValue {
    param(
        [string[]]$Lines,
        [string]$Name,
        [string]$Value
    )
    $updated = $false
    $result = foreach ($line in $Lines) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=") {
            $updated = $true
            "$Name=$Value"
        } else {
            $line
        }
    }
    if (-not $updated) {
        $result += "$Name=$Value"
    }
    return $result
}

function Ensure-DockerEnv {
    if (Test-Path $EnvFile) {
        $lines = @(Get-Content $EnvFile)
        $existingDatabaseUrl = Get-EnvFileValue -Lines $lines -Name "DATABASE_URL"
        $databaseUrl = Get-DockerDefaultDatabaseUrl
        $pg = Get-DockerPostgresSettings
        $changedEnvFile = $false
        $shouldUpgradeDatabase =
            (-not $existingDatabaseUrl) -or
            ($existingDatabaseUrl -match "^\s*sqlite") -or
            ($existingDatabaseUrl -eq "postgresql+asyncpg://agentos:agentos@postgres:5432/agentos_db")
        if ($shouldUpgradeDatabase) {
            $lines = Set-EnvFileValue -Lines $lines -Name "DATABASE_URL" -Value $databaseUrl
            $changedEnvFile = $true
        }

        $postgresDefaults = @{
            POSTGRES_USER = "agentos"
            POSTGRES_PASSWORD = "agentos"
            POSTGRES_DB = "agentos_db"
        }
        $postgresTargets = @{
            POSTGRES_USER = $pg.User
            POSTGRES_PASSWORD = $pg.Password
            POSTGRES_DB = $pg.Database
        }
        foreach ($name in $postgresTargets.Keys) {
            $existingValue = Get-EnvFileValue -Lines $lines -Name $name
            if ((-not $existingValue) -or $existingValue -eq $postgresDefaults[$name]) {
                $lines = Set-EnvFileValue -Lines $lines -Name $name -Value $postgresTargets[$name]
                $changedEnvFile = $true
            }
        }

        if ($changedEnvFile) {
            Set-Content -LiteralPath $EnvFile -Value $lines -Encoding UTF8
            Write-Host "[mydow] upgraded DATABASE_URL in $EnvFile to the docker Postgres service"
        }
        Write-Host "[mydow] using existing $EnvFile"
        return
    }

    $apiKey = Get-ProjectEnvValue "DEEPSEEK_API_KEY"
    if (-not $apiKey) { $apiKey = Get-ProjectEnvValue "API_KEY" }
    $apiBase = Get-ProjectEnvValue "LLM_BASE_URL"
    if (-not $apiBase) { $apiBase = Get-ProjectEnvValue "DEEPSEEK_OPENAI_BASE_URL" }
    if (-not $apiBase) { $apiBase = Get-ProjectEnvValue "API_BASE" }
    if (-not $apiBase) { $apiBase = "https://api.deepseek.com" }
    $model = Get-ProjectEnvValue "LLM_MODEL"
    if (-not $model) { $model = Get-ProjectEnvValue "MODEL" }
    if (-not $model) { $model = Get-ProjectEnvValue "DEEPSEEK_MODEL" }
    if (-not $model) { $model = "deepseek-v4-flash" }
    $modelFallback = Get-ProjectEnvValue "LLM_MODEL_FALLBACK"
    if (-not $modelFallback) { $modelFallback = Get-ProjectEnvValue "MODEL_FALLBACK" }
    if (-not $modelFallback) { $modelFallback = "deepseek-v4-pro" }
    $databaseUrl = Get-ProjectEnvValue "DATABASE_URL"
    if (-not $databaseUrl) {
        $databaseUrl = Get-DockerDefaultDatabaseUrl
    }
    $pg = Get-DockerPostgresSettings

    $content = @(
        "# Generated by run-mydow.cmd. Do not commit this file.",
        "SECRET_KEY=$(New-Secret)",
        "JWT_SECRET_KEY=$(New-Secret)",
        "FIELD_ENCRYPTION_KEY=",
        "DATABASE_URL=$databaseUrl",
        "AGENTOS_DEMO_MODE=on",
        "AGENTOS_PRD10_WORKER=on",
        "AGENTOS_AI_LLM=on",
        "AGENTOS_AI_TEMPERATURE=0.3",
        "AGENTOS_AI_MAX_TOKENS=2000",
        "API_KEY=$apiKey",
        "LLM_BASE_URL=$apiBase",
        "LLM_MODEL=$model",
        "LLM_MODEL_FALLBACK=$modelFallback",
        "DEEPSEEK_OPENAI_BASE_URL=$apiBase",
        "DEEPSEEK_MODEL=$model",
        "CAPTURE_ENRICH_MODEL=",
        "APP_PORT=$Port",
        "BASE_URL=http://localhost:$Port",
        "CORS_ORIGINS=http://localhost:$Port,http://127.0.0.1:$Port",
        "POSTGRES_USER=$($pg.User)",
        "POSTGRES_PASSWORD=$($pg.Password)",
        "POSTGRES_DB=$($pg.Database)",
        "POSTGRES_HOST_PORT=15432",
        "REDIS_PASSWORD=redis123",
        "REDIS_HOST_PORT=16379",
        "ENVIRONMENT=production",
        "LOG_LEVEL=info"
    )
    Set-Content -LiteralPath $EnvFile -Value $content -Encoding UTF8
    Write-Host "[mydow] generated $EnvFile"
    if (-not $apiKey) {
        Write-Host "[mydow] warning: no API_KEY/DEEPSEEK_API_KEY found in environment or .env; LLM endpoints need a real key." -ForegroundColor Yellow
    }
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker compose --env-file $EnvFile -f $ComposeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($ComposeArgs -join ' ')"
    }
}

function Wait-Healthy {
    Write-Host "[mydow] waiting for backend health: $HealthUrl"
    for ($i = 1; $i -le 90; $i++) {
        try {
            $resp = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
            if ($resp.status -eq "healthy") {
                Write-Host "[mydow] backend is healthy"
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    Invoke-Compose @("logs", "--tail", "120", "app")
    throw "backend did not become healthy"
}

function Wait-DatabaseReady {
    $probe = @"
import asyncio
from sqlalchemy import text
from agent_os.db.base import get_sessionmaker

async def main():
    async with get_sessionmaker()() as db:
        await db.execute(text("select 1 from prd10_jobs limit 1"))

asyncio.run(main())
"@
    $encodedProbe = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probe))
    $python = "import base64; exec(base64.b64decode('$encodedProbe').decode('utf-8'))"

    Write-Host "[mydow] waiting for database schema"
    for ($i = 1; $i -le 45; $i++) {
        & docker compose --env-file $EnvFile -f $ComposeFile exec -T app python -c $python 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[mydow] database schema is ready"
            return
        }
        Start-Sleep -Seconds 2
    }

    Invoke-Compose @("logs", "--tail", "160", "app")
    throw "database schema is not ready; check DATABASE_URL, migrations, and model compatibility"
}

Set-Location $Root

try {
    # `docker info` can write engine warnings to stderr and make `$?` false
    # even with exit code 0 on Windows PowerShell. `docker ps` is the quiet
    # availability probe we actually need here.
    & docker ps 1>$null 2>$null
    $dockerOk = ($LASTEXITCODE -eq 0)
} catch {
    $dockerOk = $false
}
if (-not $dockerOk) {
    Write-Host "[mydow] Docker is not running. Start Docker Desktop and rerun run-mydow.cmd." -ForegroundColor Red
    exit 1
}

Ensure-DockerEnv

$upArgs = @("up", "-d")
if (-not $NoBuild) { $upArgs += "--build" }
$upArgs += @("app", "postgres", "redis")
Invoke-Compose $upArgs

Wait-Healthy
Wait-DatabaseReady

if (-not $NoSeed) {
    Write-Host "[mydow] seeding demo data into the real persisted database"
    Invoke-Compose @("exec", "-T", "app", "python", "scripts/seed_prd10.py")
}

Write-Host ""
Write-Host "[mydow] ready: $FrontendUrl" -ForegroundColor Green
Write-Host "[mydow] stop:  docker compose --env-file .env.docker.local -f docker-compose.prd10.yml down"
Write-Host ""

if (-not $NoOpen) {
    Start-Process $FrontendUrl
}
