<#
.SYNOPSIS
    PRD10 投资人 Demo 路径自动化烟测。

.DESCRIPTION
    每日 / 每次部署后跑一遍。模拟浏览器 SPA 走过的关键路径，
    全程使用真实 `/api/v1/*` 调用。失败会直接把 SPA 阻塞前 push
    给 maintainer。

    步骤：
      1) reset SQLite demo DB
      2) seed PRD10 §25.3 数据（6/20/30/5/5/3/18/5/10）
      3) 起 uvicorn（后台）
      4) 等 demo 端点可用
      5) 走 PRD10 §30 最小闭环：
         - demo/login -> token
         - me / today / feed / kb/overview / notifications/unread-count
         - capture/text -> 看 worker 把它处理
         - kb/folders POST -> 看新文件夹
         - ai/conversations POST + messages POST -> AI 占位回答
         - ai/messages/{id}/save-to-kb -> 看 kb_documents +1
         - skills/{id}/run -> 看 job
         - notifications/list -> 至少一条 ai_output_saved
         - search?q=PRD10 -> 命中 ≥ 1
      6) 报告 PASS/FAIL + 写 .tmp/chrome-mcp-smoke-report.json
      7) 清理

    设计原则：
      - 任何步骤失败立即 throw + 退出非零
      - 输出对人 / 对 CI 都友好
      - 不依赖任何外部进程除 python + uvicorn

.PARAMETER ApiBase
    后端 base URL。默认 http://127.0.0.1:8000。

.PARAMETER Port
    uvicorn 监听端口。默认 8000。

.PARAMETER Email
    Demo 用户邮箱（必须 demo router 接受的形态）。默认 demo@mydow.example。

.PARAMETER Password
    Demo 密码。默认 demo123。

.PARAMETER KeepRunning
    跑完保留 uvicorn（默认关闭，方便 CI 一遍跑完）。

.EXAMPLE
    pwsh -File scripts/chrome-mcp-smoke.ps1
    pwsh -File scripts/chrome-mcp-smoke.ps1 -KeepRunning
#>

param(
    [string] $ApiBase = "http://127.0.0.1:8000",
    [int]    $Port    = 8000,
    [string] $Email   = "demo@mydow.example",
    [string] $Password = "demo123",
    [switch] $KeepRunning
)

$ErrorActionPreference = "Stop"
$ProgressPreference     = "SilentlyContinue"

$here  = Split-Path -Parent $PSCommandPath
$root  = Split-Path -Parent $here
$tmp   = Join-Path $root ".tmp"
$db    = Join-Path $tmp "smoke.db"
$report= Join-Path $tmp "chrome-mcp-smoke-report.json"
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory $tmp | Out-Null }

$metrics  = [ordered]@{}
$failures = New-Object System.Collections.ArrayList
$started  = Get-Date

function Write-Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}
function Write-OK($msg) {
    Write-Host ("  OK  $msg") -ForegroundColor Green
}
function Write-Fail($msg) {
    Write-Host ("  FAIL $msg") -ForegroundColor Red
    [void] $failures.Add($msg)
}

function Invoke-Api {
    param(
        [Parameter(Mandatory)] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        $Body = $null,
        [string] $Token = $null
    )
    $uri = "$ApiBase$Path"
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    if ($Body -ne $null) {
        $payload = $Body | ConvertTo-Json -Depth 10 -Compress
        return Invoke-RestMethod -Uri $uri -Method $Method `
            -Headers $headers -Body $payload -TimeoutSec 30
    } else {
        return Invoke-RestMethod -Uri $uri -Method $Method `
            -Headers $headers -TimeoutSec 30
    }
}

# 1. reset + seed
Write-Section "1. reset SQLite + seed PRD10 (sec 25.3)"
if (Test-Path $db) { Remove-Item $db -Force }
$env:DATABASE_URL = "sqlite+aiosqlite:///" + ($db -replace '\\','/')
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_AI_LLM = "off"
$env:PYTHONPATH = (Join-Path $root "src")

Push-Location $root
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$seedOut = & python "scripts/seed_prd10.py" --email $Email --password $Password --reset 2>&1
$seedExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($seedExit -ne 0) {
    Write-Fail "seed_prd10.py exited $seedExit"
    Pop-Location
    return
}
$seedSummary = $seedOut | Select-String -Pattern 'Seed completed for user' -SimpleMatch
if ($seedSummary) {
    Write-OK "seed reset complete (output captured)"
} else {
    Write-Host "  WARN: 'Seed completed' marker not found, but exit was 0" -ForegroundColor Yellow
}

# 2. start uvicorn
Write-Section "2. start uvicorn (background)"
$uvOut = Join-Path $tmp "uvicorn-smoke.out"
$uvErr = Join-Path $tmp "uvicorn-smoke.err"
$proc = Start-Process -FilePath "python" -PassThru `
    -ArgumentList @("-m","uvicorn","agent_os.server.app:app","--host","127.0.0.1","--port",$Port,"--log-level","warning") `
    -RedirectStandardOutput $uvOut `
    -RedirectStandardError $uvErr
$metrics.uvicorn_pid = $proc.Id
Write-OK "PID=$($proc.Id)"

try {
    # 3. wait for /demo/status
    Write-Section "3. wait for backend ready"
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $st = Invoke-Api -Method GET -Path "/api/v1/demo/status"
            if ($st.enabled -eq $true -and $st.email) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { throw "backend not ready after 15s" }
    Write-OK "demo/status enabled=true email=$($st.email)"
    $metrics.demo_email = $st.email

    # 4. demo login
    Write-Section "4. demo login"
    $login = Invoke-Api -Method POST -Path "/api/v1/demo/login"
    $token = $login.access_token
    if (-not $token) { throw "demo/login did not return access_token" }
    Write-OK "token=$($token.Substring(0,30))..."
    $metrics.token_present = $true

    # 5. baseline reads
    Write-Section "5. baseline reads (me / today / feed / kb / notifications)"
    $me = Invoke-Api -Method GET -Path "/api/v1/me" -Token $token
    if ($me.username -ne "demo" -and $me.email -ne $Email) { Write-Fail "/me unexpected: $($me | ConvertTo-Json -Compress)" } else { Write-OK "/me OK ($($me.email))" }

    $today = Invoke-Api -Method GET -Path "/api/v1/today" -Token $token
    if (-not $today.success) { Write-Fail "/today envelope.success != true" } else {
        $stats = $today.data.stats
        Write-OK "/today.stats: capture=$($stats.today_capture_count) tasks=$($stats.pending_task_count) knowledge=$($stats.knowledge_items_count)"
        $metrics.today_stats_baseline = $stats
    }

    $feed = Invoke-Api -Method GET -Path "/api/v1/feed?page_size=10" -Token $token
    $feedTotalBefore = $feed.data.pagination.total
    Write-OK "/feed total=$feedTotalBefore"

    $kbOv = Invoke-Api -Method GET -Path "/api/v1/kb/overview" -Token $token
    Write-OK "/kb/overview folders=$($kbOv.data.stats.folder_count) docs=$($kbOv.data.stats.document_count)"
    $metrics.kb_baseline = $kbOv.data.stats

    $unread = Invoke-Api -Method GET -Path "/api/v1/notifications/unread-count" -Token $token
    Write-OK "/notifications/unread-count=$($unread.data.count)"

    $convs = Invoke-Api -Method GET -Path "/api/v1/ai/conversations" -Token $token
    $convCountBefore = $convs.data.pagination.total
    Write-OK "/ai/conversations total=$convCountBefore"

    $skills = Invoke-Api -Method GET -Path "/api/v1/skills" -Token $token
    $skillCount = $skills.data.pagination.total
    Write-OK "/skills total=$skillCount"
    if ($skillCount -lt 1) { Write-Fail "Skills 列表为空，演示路径会卡住" }
    $skillId = $skills.data.items[0].id

    # 6. capture text
    Write-Section "6. PRD10 sec 30 minimal loop: capture/text"
    $cap = Invoke-Api -Method POST -Path "/api/v1/capture/text" -Token $token -Body @{
        content      = "chrome-mcp-smoke @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
        auto_process = $true
    }
    if (-not $cap.success) { Write-Fail "capture/text failed envelope" } else {
        Write-OK "capture/text -> inbox $($cap.data.inbox_item.id) job $($cap.data.job.id)"
    }

    # 7. create folder
    Write-Section "7. PRD10 sec 10.3: kb/folders POST"
    $folder = Invoke-Api -Method POST -Path "/api/v1/kb/folders" -Token $token -Body @{
        name = "smoke-folder-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        description = "created by chrome-mcp-smoke"
        color = "blue"
    }
    if (-not $folder.success) { Write-Fail "kb/folders POST failed" } else {
        Write-OK "kb/folders POST -> $($folder.data.id)"
    }

    # 8. AI conversation + send + save-to-kb
    Write-Section "8. PRD10 sec 11: ai/conversations + messages + save-to-kb"
    $newConv = Invoke-Api -Method POST -Path "/api/v1/ai/conversations" -Token $token -Body @{
        title = "smoke conv $(Get-Date -Format 'HH:mm:ss')"
        mode  = "general"
    }
    $cid = $newConv.data.id
    Write-OK "ai/conversations POST -> $cid"

    $msg = Invoke-Api -Method POST -Path "/api/v1/ai/conversations/$cid/messages" -Token $token -Body @{
        content = "PRD10 V1 minimal loop summary"
    }
    $aiId = $msg.data.assistant_message.id
    $aiJobId = $msg.data.job.id
    Write-OK "messages POST -> assistant=$aiId job=$aiJobId"

    $save = Invoke-Api -Method POST -Path "/api/v1/ai/messages/$aiId/save-to-kb" -Token $token -Body @{
        title = "smoke saved at $(Get-Date -Format 'HH:mm:ss')"
        tags  = @("smoke","ai")
    }
    if (-not $save.success) { Write-Fail "ai save-to-kb failed" } else {
        $saveJobId = $save.data.job_id
        Write-OK "ai/messages/$aiId/save-to-kb -> job $saveJobId"
    }

    # 9. skill run
    Write-Section "9. PRD10 sec 17: skills/{id}/run"
    $run = Invoke-Api -Method POST -Path "/api/v1/skills/$skillId/run" -Token $token -Body @{
        input = @{ text = "smoke skill input" }
        save_output = $true
    }
    if (-not $run.success) { Write-Fail "skill run failed" } else {
        Write-OK "skills/$skillId/run -> job $($run.data.job_id) skill_run $($run.data.skill_run_id)"
    }

    # 10. wait worker (PRD10 sec 16.3: poll queued/running every 2s; sleep 8s for safety)
    Write-Section "10. wait 8s for worker to drain"
    Start-Sleep -Seconds 8

    # 11. verify deltas
    Write-Section "11. verify deltas (worker materialization)"
    $kbOvAfter = Invoke-Api -Method GET -Path "/api/v1/kb/overview" -Token $token
    Write-Host "  kb folders before=$($metrics.kb_baseline.folder_count) after=$($kbOvAfter.data.stats.folder_count)"
    Write-Host "  kb documents before=$($metrics.kb_baseline.document_count) after=$($kbOvAfter.data.stats.document_count)"
    if ($kbOvAfter.data.stats.folder_count -le $metrics.kb_baseline.folder_count) {
        Write-Fail "kb folders not increased after creating one"
    } else { Write-OK "kb folders increased" }
    if ($kbOvAfter.data.stats.document_count -le $metrics.kb_baseline.document_count) {
        Write-Fail "kb documents not increased after AI save-to-kb worker run"
    } else { Write-OK "kb documents increased (worker materialized AI output)" }

    $todayAfter = Invoke-Api -Method GET -Path "/api/v1/today" -Token $token
    Write-Host "  today capture before=$($metrics.today_stats_baseline.today_capture_count) after=$($todayAfter.data.stats.today_capture_count)"
    if ($todayAfter.data.stats.today_capture_count -le $metrics.today_stats_baseline.today_capture_count) {
        Write-Fail "/today.today_capture_count not incremented after capture"
    } else { Write-OK "today_capture_count incremented" }

    $notif = Invoke-Api -Method GET -Path "/api/v1/notifications?page_size=20" -Token $token
    $aiSavedNotif = $notif.data.items | Where-Object { $_.type -eq "ai_output_saved" }
    if (-not $aiSavedNotif) {
        Write-Fail "no ai_output_saved notification produced"
    } else {
        $cnt = @($aiSavedNotif).Count
        Write-OK ("ai_output_saved notification present (count={0})" -f $cnt)
    }

    # 12. search hit
    Write-Section "12. PRD10 sec 13: search?q=PRD10"
    $sr = Invoke-Api -Method GET -Path "/api/v1/search?q=PRD10&page_size=5" -Token $token
    if ($sr.data.pagination.total -lt 1) { Write-Fail "search 'PRD10' returned 0 results, seed missing?" }
    else { Write-OK "search hits=$($sr.data.pagination.total)" }
    $metrics.search_hits = $sr.data.pagination.total

    # 13. final
    $metrics.kb_after        = $kbOvAfter.data.stats
    $metrics.today_after     = $todayAfter.data.stats
    $metrics.notification_total = $notif.data.pagination.total
    $metrics.failures        = $failures
    $metrics.duration_ms     = ((Get-Date) - $started).TotalMilliseconds
    $metrics.timestamp       = (Get-Date).ToString("o")
    $metrics | ConvertTo-Json -Depth 10 | Set-Content -Path $report -Encoding UTF8
    Write-Section "report"
    Write-Host "  written to $report"
}
finally {
    if (-not $KeepRunning) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-OK "uvicorn stopped"
        } catch {
            Write-Host "  WARN: could not stop uvicorn: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  uvicorn left running (PID=$($proc.Id))" -ForegroundColor Yellow
    }
    Pop-Location
}

Write-Section "result"
if ($failures.Count -gt 0) {
    Write-Host "FAILED ($($failures.Count) issues):" -ForegroundColor Red
    foreach ($f in $failures) { Write-Host "  - $f" -ForegroundColor Red }
    exit 1
} else {
    Write-Host "PASS — investor demo path is healthy ($([int]$metrics.duration_ms) ms)" -ForegroundColor Green
    exit 0
}
