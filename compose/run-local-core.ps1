# Requires: Python 3.12+, Node.js 20+
# From monorepo root: .\compose\run-local-core.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "packages\py-alama-common"))) {
    $Root = $PSScriptRoot + "\.."
}
Set-Location $Root

$py = $env:ALAMA_PYTHON
if (-not $py) {
    $candidates = @(
        "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "python"
    )
    foreach ($c in $candidates) {
        if ($c -eq "python") { $py = "python"; break }
        if (Test-Path $c) { $py = $c; break }
    }
}

Write-Host "Installing Python packages..." -ForegroundColor Cyan
& $py -m pip install -e "packages/py-alama-common[fastapi]" -q
& $py -m pip install -e "services/identity-service[dev]" -q
& $py -m pip install -e "services/api-gateway[dev]" -q
& $py -m pip install -e "services/bff-web[dev]" -q

Write-Host "Installing web deps..." -ForegroundColor Cyan
Push-Location (Join-Path $Root "apps\web")
if (-not (Test-Path "node_modules")) {
    npm install
}
Pop-Location

$env:IDENTITY_USE_IN_MEMORY_STORE = "true"
$env:IDENTITY_OTEL_ENABLED = "false"
$env:GATEWAY_USE_ECHO_UPSTREAM = "true"
$env:GATEWAY_OTEL_ENABLED = "false"
$env:BFF_USE_IN_MEMORY_CLIENTS = "true"
$env:BFF_OTEL_ENABLED = "false"

Write-Host "Starting identity-service :8101" -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "identity_service.main:app", "--host", "127.0.0.1", "--port", "8101"
) -WorkingDirectory $Root -WindowStyle Minimized

Write-Host "Starting api-gateway :18080 (8080 often reserved on Windows)" -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "api_gateway.main:app", "--host", "127.0.0.1", "--port", "18080"
) -WorkingDirectory $Root -WindowStyle Minimized

Write-Host "Starting bff-web :8081" -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "bff_web.main:app", "--host", "127.0.0.1", "--port", "8081"
) -WorkingDirectory $Root -WindowStyle Minimized

Write-Host "Starting alama-web :3000" -ForegroundColor Green
Start-Process -FilePath "npm" -ArgumentList @("run", "dev") `
    -WorkingDirectory (Join-Path $Root "apps\web") -WindowStyle Minimized

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "Core stack starting (in-memory stores):" -ForegroundColor Cyan
Write-Host "  Web UI        http://localhost:3000"
Write-Host "  API Gateway   http://localhost:18080/health"
Write-Host "  BFF           http://localhost:8081/health"
Write-Host "  Identity      http://localhost:8101/health"
Write-Host "  Identity docs http://localhost:8101/docs"
Write-Host ""
Write-Host "Stop: close the minimized windows or end the uvicorn/node processes."
