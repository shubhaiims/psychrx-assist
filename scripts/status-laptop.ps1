$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $Root ".runtime"
$PidFile = Join-Path $RuntimeDir "pids.json"

function Test-Url([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
    return "$($response.StatusCode) OK"
  } catch {
    return "not responding"
  }
}

if (!(Test-Path $PidFile)) {
  Write-Host "PsychRx Assist is not running from the local PID file."
  exit 0
}

$State = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
$BackendProcess = Get-Process -Id $State.backendPid -ErrorAction SilentlyContinue
$FrontendProcess = Get-Process -Id $State.frontendPid -ErrorAction SilentlyContinue

Write-Host "PsychRx Assist local status"
Write-Host "Started:  $($State.startedAt)"
Write-Host "Website:  $($State.frontendUrl) - $(Test-Url $State.frontendUrl)"
Write-Host "API:      $($State.backendUrl) - $(Test-Url "$($State.backendUrl)/")"
Write-Host "Backend:  PID $($State.backendPid) - $(if ($BackendProcess) { "running" } else { "not running" })"
Write-Host "Frontend: PID $($State.frontendPid) - $(if ($FrontendProcess) { "running" } else { "not running" })"
