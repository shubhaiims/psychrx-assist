$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $Root ".runtime"
$PidFile = Join-Path $RuntimeDir "pids.json"

if (!(Test-Path $PidFile)) {
  Write-Host "No local PsychRx Assist PID file found. Nothing to stop."
  exit 0
}

$State = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
$ProcessIds = @($State.frontendPid, $State.backendPid) | Where-Object { $_ }

foreach ($ProcessId in $ProcessIds) {
  Write-Host "Stopping process tree $ProcessId..."
  & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Process $ProcessId was already stopped."
  }
}

Remove-Item -Path $PidFile -Force
Write-Host "PsychRx Assist local background services stopped."
