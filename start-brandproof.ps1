# start-brandproof.ps1
# BrandProof one-command startup: FastAPI backend + React frontend in separate windows.

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"

Write-Host "Starting BrandProof..." -ForegroundColor Cyan

# Validate backend entry point
$backendEntry = Join-Path $backendPath "app\main.py"
if (-not (Test-Path -LiteralPath $backendEntry)) {
    Write-Host "ERROR: Backend entry point not found: $backendEntry" -ForegroundColor Red
    Write-Host "       The FastAPI backend is missing or not set up correctly."
    Read-Host "Press Enter to exit"
    exit 1
}

# Validate frontend package.json
$frontendPkg = Join-Path $frontendPath "package.json"
if (-not (Test-Path -LiteralPath $frontendPkg)) {
    Write-Host "ERROR: Frontend package.json not found: $frontendPkg" -ForegroundColor Red
    Write-Host "       The React frontend is missing or not set up correctly."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Backend entry point found: $backendEntry" -ForegroundColor Green
Write-Host "Frontend package.json found: $frontendPkg" -ForegroundColor Green

# Start backend in a new PowerShell window
$backendCmd = "Set-Location -Path '$backendPath'; python -m uvicorn app.main:app --reload"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-Command", $backendCmd -WorkingDirectory $projectRoot

# Start frontend in a new PowerShell window
$frontendCmd = "Set-Location -Path '$frontendPath'; npm run dev"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-Command", $frontendCmd -WorkingDirectory $projectRoot

Write-Host "BrandProof startup scripts launched." -ForegroundColor Green
Write-Host "Backend starting at http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend starting at http://localhost:5173" -ForegroundColor Yellow
