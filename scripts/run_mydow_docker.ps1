param(
    [switch]$NoOpen,
    [switch]$NoBuild,
    [switch]$NoSeed,
    [switch]$SeedDemoData,
    [switch]$NoNginx,
    [switch]$NoPrompt,
    [switch]$RequireDeepSeek,
    [int]$Port = 8000,
    [int]$HttpPort = 8080
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $Root ".env.docker.local"
$ComposeFile = Join-Path $Root "docker-compose.prd10.yml"
$AppBaseUrl = "http://localhost:$Port"
$NginxBaseUrl = "http://localhost:$HttpPort"
$BaseUrl = if ($NoNginx) { $AppBaseUrl } else { $NginxBaseUrl }
$FrontendUrl = "$BaseUrl/"
$DirectFrontendUrl = "$AppBaseUrl/mydow/biz_v14/"
$HealthUrl = "$BaseUrl/health"

function Get-EnvFileValue {
    param(
        [string[]]$Lines,
        [string]$Name
    )
    foreach ($line in $Lines) {
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
    return @($result)
}

function Get-ProjectEnvValue {
    param([string]$Name)
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($processValue) { return $processValue }

    foreach ($fileName in @(".env.local", ".env")) {
        $sourceEnv = Join-Path $Root $fileName
        if (-not (Test-Path $sourceEnv)) { continue }
        $value = Get-EnvFileValue -Lines @(Get-Content $sourceEnv) -Name $Name
        if ($value) { return $value }
    }
    return ""
}

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Read-VisibleValue {
    param(
        [string]$Prompt,
        [string]$Default = ""
    )
    if ($NoPrompt) { return $Default }
    $suffix = if ($Default) { " [$Default]" } else { "" }
    $value = Read-Host -Prompt "$Prompt$suffix"
    if (-not $value) { return $Default }
    return $value.Trim()
}

function Read-HiddenValue {
    param([string]$Prompt)
    if ($NoPrompt) { return "" }
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    if ($secure.Length -eq 0) { return "" }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Resolve-DeepSeekApiKey {
    $apiKey = Get-ProjectEnvValue "DEEPSEEK_API_KEY"
    if (-not $apiKey) { $apiKey = Get-ProjectEnvValue "API_KEY" }
    if (-not $apiKey) {
        $apiKey = Read-HiddenValue "Paste DeepSeek API Key (leave blank to start without AI)"
    }
    if (-not $apiKey -and $RequireDeepSeek) {
        throw "DEEPSEEK_API_KEY is required. Set it in the environment or rerun without -RequireDeepSeek."
    }
    return $apiKey
}

function Resolve-LlmApiBase {
    $apiBase = Get-ProjectEnvValue "LLM_BASE_URL"
    if (-not $apiBase) { $apiBase = Get-ProjectEnvValue "DEEPSEEK_OPENAI_BASE_URL" }
    if (-not $apiBase) { $apiBase = Get-ProjectEnvValue "API_BASE" }
    if (-not $apiBase) {
        $apiBase = Read-VisibleValue -Prompt "LLM API URL" -Default "https://api.deepseek.com"
    }
    return $apiBase
}

function Get-DockerDefaultDatabaseUrl {
    param(
        [string]$User,
        [string]$Password,
        [string]$Database
    )
    return "postgresql+asyncpg://$User`:$Password@postgres:5432/$Database"
}

function Ensure-DockerEnv {
    $apiKey = Resolve-DeepSeekApiKey
    $apiBase = Resolve-LlmApiBase

    $model = Get-ProjectEnvValue "LLM_MODEL"
    if (-not $model) { $model = Get-ProjectEnvValue "MODEL" }
    if (-not $model) { $model = Get-ProjectEnvValue "DEEPSEEK_MODEL" }
    if (-not $model) { $model = "deepseek-v4-flash" }

    $modelFallback = Get-ProjectEnvValue "LLM_MODEL_FALLBACK"
    if (-not $modelFallback) { $modelFallback = Get-ProjectEnvValue "MODEL_FALLBACK" }
    if (-not $modelFallback) { $modelFallback = "deepseek-v4-pro" }

    $corsOrigins = "$BaseUrl,$AppBaseUrl,http://127.0.0.1:$Port,http://127.0.0.1:$HttpPort"

    if (Test-Path $EnvFile) {
        $lines = @(Get-Content $EnvFile)
        $changed = $false

        $defaults = [ordered]@{
            SECRET_KEY = New-Secret
            JWT_SECRET_KEY = New-Secret
            FIELD_ENCRYPTION_KEY = ""
            POSTGRES_USER = "mydow"
            POSTGRES_DB = "mydow_prd10"
            POSTGRES_HOST_PORT = "15432"
            REDIS_HOST_PORT = "16379"
            ENVIRONMENT = "production"
            AGENTOS_DEMO_MODE = "off"
            AGENTOS_PRD10_WORKER = "on"
            AGENTOS_AI_LLM = "on"
            AGENTOS_AI_OFFLINE_PLACEHOLDER = "off"
            AGENTOS_AI_TEMPERATURE = "0.3"
            AGENTOS_AI_MAX_TOKENS = "2000"
            LLM_BASE_URL = $apiBase
            DEEPSEEK_OPENAI_BASE_URL = $apiBase
            LLM_MODEL = $model
            LLM_MODEL_FALLBACK = $modelFallback
            DEEPSEEK_MODEL = $model
            CAPTURE_ENRICH_MODEL = ""
            APP_PORT = "$Port"
            HTTP_PORT = "$HttpPort"
            BASE_URL = $BaseUrl
            CORS_ORIGINS = $corsOrigins
            AGENTOS_CORS_ORIGINS = $corsOrigins
            AGENTOS_CORS_ALLOW_ALL = "false"
            CORS_ALLOW_ALL = "false"
            SMTP_HOST = ""
            SMTP_PORT = "587"
            SMTP_USER = ""
            SMTP_PASS = ""
            SMTP_FROM = "noreply@localhost"
            SMTP_USE_TLS = "true"
            MYDOW_ROOT_REDIRECT = "on"
            LOG_LEVEL = "info"
        }

        foreach ($name in $defaults.Keys) {
            $existing = Get-EnvFileValue -Lines $lines -Name $name
            if (-not $existing -or $name -in @("APP_PORT", "HTTP_PORT", "BASE_URL", "CORS_ORIGINS", "AGENTOS_CORS_ORIGINS", "MYDOW_ROOT_REDIRECT", "AGENTOS_DEMO_MODE", "AGENTOS_AI_OFFLINE_PLACEHOLDER")) {
                $lines = Set-EnvFileValue -Lines $lines -Name $name -Value $defaults[$name]
                $changed = $true
            }
        }

        $pgUser = Get-EnvFileValue -Lines $lines -Name "POSTGRES_USER"
        $pgPass = Get-EnvFileValue -Lines $lines -Name "POSTGRES_PASSWORD"
        $pgDb = Get-EnvFileValue -Lines $lines -Name "POSTGRES_DB"
        if (-not $pgPass) {
            $pgPass = New-Secret
            $lines = Set-EnvFileValue -Lines $lines -Name "POSTGRES_PASSWORD" -Value $pgPass
            $changed = $true
        }
        if (-not (Get-EnvFileValue -Lines $lines -Name "DATABASE_URL")) {
            $lines = Set-EnvFileValue -Lines $lines -Name "DATABASE_URL" -Value (Get-DockerDefaultDatabaseUrl -User $pgUser -Password $pgPass -Database $pgDb)
            $changed = $true
        }
        if (-not (Get-EnvFileValue -Lines $lines -Name "REDIS_PASSWORD")) {
            $lines = Set-EnvFileValue -Lines $lines -Name "REDIS_PASSWORD" -Value (New-Secret)
            $changed = $true
        }
        if ($apiKey) {
            foreach ($name in @("API_KEY", "DEEPSEEK_API_KEY")) {
                if (-not (Get-EnvFileValue -Lines $lines -Name $name)) {
                    $lines = Set-EnvFileValue -Lines $lines -Name $name -Value $apiKey
                    $changed = $true
                }
            }
        }

        if ($changed) {
            Set-Content -LiteralPath $EnvFile -Value $lines -Encoding UTF8
            Write-Host "[mydow] updated $EnvFile"
        } else {
            Write-Host "[mydow] using existing $EnvFile"
        }
        if (-not (Get-EnvFileValue -Lines $lines -Name "DEEPSEEK_API_KEY") -and -not (Get-EnvFileValue -Lines $lines -Name "API_KEY")) {
            Write-Host "[mydow] warning: no DeepSeek key configured; AI calls will fail until DEEPSEEK_API_KEY is set." -ForegroundColor Yellow
        }
        return
    }

    $pgUser = "mydow"
    $pgPass = New-Secret
    $pgDb = "mydow_prd10"
    $redisPass = New-Secret
    $databaseUrl = Get-DockerDefaultDatabaseUrl -User $pgUser -Password $pgPass -Database $pgDb

    $content = @(
        "# Generated by run-mydow. Do not commit this file.",
        "SECRET_KEY=$(New-Secret)",
        "JWT_SECRET_KEY=$(New-Secret)",
        "FIELD_ENCRYPTION_KEY=",
        "DATABASE_URL=$databaseUrl",
        "POSTGRES_USER=$pgUser",
        "POSTGRES_PASSWORD=$pgPass",
        "POSTGRES_DB=$pgDb",
        "POSTGRES_HOST_PORT=15432",
        "REDIS_PASSWORD=$redisPass",
        "REDIS_HOST_PORT=16379",
        "ENVIRONMENT=production",
        "AGENTOS_DEMO_MODE=off",
        "AGENTOS_PRD10_WORKER=on",
        "AGENTOS_AI_LLM=on",
        "AGENTOS_AI_OFFLINE_PLACEHOLDER=off",
        "AGENTOS_AI_TEMPERATURE=0.3",
        "AGENTOS_AI_MAX_TOKENS=2000",
        "API_KEY=$apiKey",
        "DEEPSEEK_API_KEY=$apiKey",
        "LLM_BASE_URL=$apiBase",
        "LLM_MODEL=$model",
        "LLM_MODEL_FALLBACK=$modelFallback",
        "DEEPSEEK_OPENAI_BASE_URL=$apiBase",
        "DEEPSEEK_MODEL=$model",
        "CAPTURE_ENRICH_MODEL=",
        "APP_PORT=$Port",
        "HTTP_PORT=$HttpPort",
        "BASE_URL=$BaseUrl",
        "CORS_ORIGINS=$corsOrigins",
        "AGENTOS_CORS_ORIGINS=$corsOrigins",
        "AGENTOS_CORS_ALLOW_ALL=false",
        "CORS_ALLOW_ALL=false",
        "SMTP_HOST=",
        "SMTP_PORT=587",
        "SMTP_USER=",
        "SMTP_PASS=",
        "SMTP_FROM=noreply@localhost",
        "SMTP_USE_TLS=true",
        "MYDOW_ROOT_REDIRECT=on",
        "LOG_LEVEL=info"
    )
    Set-Content -LiteralPath $EnvFile -Value $content -Encoding UTF8
    Write-Host "[mydow] generated $EnvFile"
    if (-not $apiKey) {
        Write-Host "[mydow] warning: no DeepSeek key configured; AI calls will fail until DEEPSEEK_API_KEY is set." -ForegroundColor Yellow
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

if ($NoNginx) {
    $upArgs = @("up", "-d")
    if (-not $NoBuild) { $upArgs += "--build" }
    $upArgs += @("app", "postgres", "redis")
} else {
    $upArgs = @("--profile", "nginx", "up", "-d")
    if (-not $NoBuild) { $upArgs += "--build" }
    $upArgs += @("app", "postgres", "redis", "nginx")
}
Invoke-Compose $upArgs

Wait-Healthy
Wait-DatabaseReady

if ($SeedDemoData -and -not $NoSeed) {
    Write-Host "[mydow] seeding optional demo data into the persisted database"
    Invoke-Compose @("exec", "-T", "app", "python", "scripts/seed_prd10.py")
}

Write-Host ""
Write-Host "[mydow] ready: $FrontendUrl" -ForegroundColor Green
Write-Host "[mydow] direct app URL: $DirectFrontendUrl"
Write-Host "[mydow] env file: $EnvFile"
Write-Host "[mydow] stop: docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down"
Write-Host "[mydow] reset data: docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down -v"
Write-Host ""

if (-not $NoOpen) {
    Start-Process $FrontendUrl
}
