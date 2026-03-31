# start.ps1 — run from anywhere: .\start.ps1  or  bmo\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$venv = Join-Path $backend "venv\Scripts\Activate.ps1"

if (-not (Test-Path $venv)) {
    Write-Error "venv not found at $venv"
    exit 1
}

Write-Host "Activating venv..." -ForegroundColor Cyan
. $venv

Write-Host "Starting BMO..." -ForegroundColor Green
Set-Location $backend
fastapi dev
