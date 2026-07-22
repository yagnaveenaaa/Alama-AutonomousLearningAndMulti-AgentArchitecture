# Requires: Python 3.12+, Node.js 20+
# From monorepo root: .\compose\run-vertical-slice.ps1
#
# Boots BFF with the live vertical slice + Next.js web UI.
# Chat "Fix authentication bug" → import → index → plan → edit → pytest → approve → local PR.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = $env:ALAMA_PYTHON
if (-not $py) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
        "python"
    )
    foreach ($c in $candidates) {
        if ($c -eq "python") { $py = "python"; break }
        if (Test-Path $c) { $py = $c; break }
    }
}

Write-Host "Installing vertical-slice Python packages..." -ForegroundColor Cyan
& $py -m pip install -e "packages/py-alama-common[fastapi]" -q
& $py -m pip install -e "workers/indexing-worker" -q
& $py -m pip install -e "workers/agent-worker" -q
& $py -m pip install -e "packages/py-alama-slice" -q
& $py -m pip install -e "services/bff-web[dev]" -q
& $py -m pip install pytest -q

Write-Host "Installing web deps..." -ForegroundColor Cyan
Push-Location (Join-Path $Root "apps\web")
if (-not (Test-Path "node_modules")) {
    npm install
}
Pop-Location

$env:BFF_ENABLE_VERTICAL_SLICE = "true"
$env:BFF_USE_IN_MEMORY_CLIENTS = "false"
$env:BFF_OTEL_ENABLED = "false"
$env:BFF_FIXTURE_DIR = (Join-Path $Root "fixtures\auth-bug-repo")
$env:NEXT_PUBLIC_BFF_URL = "http://127.0.0.1:8081"

Write-Host "Starting bff-web (vertical slice) :8081" -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "bff_web.main:app", "--host", "127.0.0.1", "--port", "8081"
) -WorkingDirectory $Root -WindowStyle Minimized

Write-Host "Starting alama-web :3000" -ForegroundColor Green
Start-Process -FilePath "npm" -ArgumentList @("run", "dev") `
    -WorkingDirectory (Join-Path $Root "apps\web") -WindowStyle Minimized

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Vertical slice stack:" -ForegroundColor Cyan
Write-Host "  Web UI     http://localhost:3000  (login → Chat → Fix authentication bug)"
Write-Host "  BFF        http://localhost:8081/health"
Write-Host "  GraphiQL   http://localhost:8081/graphql"
Write-Host ""
Write-Host "Headless alternative:" -ForegroundColor Cyan
Write-Host "  alama-slice run --objective `"Fix authentication bug`" --auto-approve"
Write-Host ""
Write-Host "Stop: close the minimized windows or end the uvicorn/node processes."
