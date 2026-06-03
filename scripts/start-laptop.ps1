param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8000,
  [string]$HostName = "127.0.0.1",
  [switch]$Install,
  [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$RuntimeDir = Join-Path $Root ".runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PidFile = Join-Path $RuntimeDir "pids.json"

$BackendUrl = "http://${HostName}:${BackendPort}"
$FrontendUrl = "http://${HostName}:${FrontendPort}"

function Repair-ProcessPath {
  $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "Process")
  if ([string]::IsNullOrWhiteSpace($CurrentPath)) {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $CurrentPath = @($MachinePath, $UserPath) -join ";"
  }

  [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
  [Environment]::SetEnvironmentVariable("Path", $CurrentPath, "Process")
}

function Ensure-Dir([string]$Path) {
  if (!(Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Test-ListeningPort([int]$Port) {
  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  return $null -ne $connection
}

function Wait-HttpOk([string]$Url, [int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  return $false
}

function Test-ProcessAlive([int]$ProcessId) {
  return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

Ensure-Dir $RuntimeDir
Ensure-Dir $LogDir
Repair-ProcessPath

if (Test-Path $PidFile) {
  $ExistingState = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
  $BackendAlive = Test-ProcessAlive ([int]$ExistingState.backendPid)
  $FrontendAlive = Test-ProcessAlive ([int]$ExistingState.frontendPid)
  if ($BackendAlive -or $FrontendAlive) {
    throw "PsychRx Assist appears to already be running. Run scripts\stop-laptop.ps1 first."
  }

  Remove-Item -Path $PidFile -Force
}

if (Test-ListeningPort $BackendPort) {
  throw "Port $BackendPort is already in use. Stop the existing backend or choose another BackendPort."
}

if (Test-ListeningPort $FrontendPort) {
  throw "Port $FrontendPort is already in use. Stop the existing frontend or choose another FrontendPort."
}

$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
  Write-Host "Creating backend virtual environment..."
  Push-Location $BackendDir
  python -m venv .venv
  Pop-Location
}

if ($Install -or !(Test-Path $Python)) {
  Write-Host "Installing backend dependencies..."
  Push-Location $BackendDir
  & $Python -m pip install -r requirements.txt
  Pop-Location
}

if ($Install -or !(Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Host "Installing frontend dependencies..."
  Push-Location $FrontendDir
  & "C:\Program Files\nodejs\npm.cmd" install --ignore-scripts --cache .npm-cache --no-audit --no-fund
  Pop-Location
}

$env:API_BASE_URL = $BackendUrl
$env:NEXT_PUBLIC_API_BASE = "/api"
$env:NEXT_PUBLIC_SITE_URL = $FrontendUrl
$env:NEXT_PUBLIC_SENTRY_DSN = ""
$env:SENTRY_DSN = ""

if ($Rebuild -or !(Test-Path (Join-Path $FrontendDir ".next"))) {
  Write-Host "Building frontend for local laptop mode..."
  Push-Location $FrontendDir
  & "C:\Program Files\nodejs\npm.cmd" run build
  Pop-Location
}

$BackendOut = Join-Path $LogDir "backend.out.log"
$BackendErr = Join-Path $LogDir "backend.err.log"
$FrontendOut = Join-Path $LogDir "frontend.out.log"
$FrontendErr = Join-Path $LogDir "frontend.err.log"

Write-Host "Starting backend in the background..."
$env:CORS_ALLOW_ORIGINS = "$FrontendUrl,http://localhost:$FrontendPort"
$env:RULE_STORE_DATABASE_URL = ""
$env:SENTRY_DSN = ""
$BackendArgs = "-m uvicorn app.main:app --host $HostName --port $BackendPort"
$BackendProcess = Start-Process -FilePath $Python -ArgumentList $BackendArgs -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr

if (!(Wait-HttpOk "$BackendUrl/" 45)) {
  Write-Host "Backend did not answer in time. Check $BackendErr"
}

Write-Host "Starting frontend in the background..."
$env:API_BASE_URL = $BackendUrl
$env:NEXT_PUBLIC_API_BASE = "/api"
$env:NEXT_PUBLIC_SITE_URL = $FrontendUrl
$env:NEXT_PUBLIC_SENTRY_DSN = ""
$env:SENTRY_DSN = ""
$FrontendArgs = ".\node_modules\next\dist\bin\next start --hostname $HostName --port $FrontendPort"
$FrontendProcess = Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList $FrontendArgs -WorkingDirectory $FrontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr

if (!(Wait-HttpOk "$FrontendUrl/" 60)) {
  Write-Host "Frontend did not answer in time. Check $FrontendErr"
}

$State = [ordered]@{
  backendPid = $BackendProcess.Id
  frontendPid = $FrontendProcess.Id
  backendUrl = $BackendUrl
  frontendUrl = $FrontendUrl
  startedAt = (Get-Date).ToString("s")
}

$State | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ""
Write-Host "PsychRx Assist is running locally."
Write-Host "Website: $FrontendUrl"
Write-Host "API:     $BackendUrl"
Write-Host "Logs:    $LogDir"
Write-Host ""
Write-Host "To stop it later, run: powershell -ExecutionPolicy Bypass -File scripts\stop-laptop.ps1"
