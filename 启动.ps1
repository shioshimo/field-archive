$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
  $taskSystemPython = Get-Command python -ErrorAction SilentlyContinue
  if ($taskSystemPython) { $taskPython = $taskSystemPython.Source }
  else { $taskPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
}
if (-not (Test-Path -LiteralPath $taskPython)) { throw '请先安装 Python，再按 README 安装依赖。' }
$taskPort = 8770
$taskConfig = Join-Path $PSScriptRoot 'config.local.json'
if (Test-Path -LiteralPath $taskConfig) {
  $taskSettings = Get-Content -LiteralPath $taskConfig -Raw | ConvertFrom-Json
  if ($taskSettings.port) { $taskPort = [int]$taskSettings.port }
}
$taskUrl = 'http://127.0.0.1:' + $taskPort + '/'
$taskRunning = $false
try { $taskResult = Invoke-RestMethod -Uri ($taskUrl + 'api/catalog') -TimeoutSec 2; $taskRunning = $taskResult.schemaVersion -eq 1 } catch {}
if (-not $taskRunning) {
  Start-Process -FilePath $taskPython -ArgumentList @('-u', ('"' + (Join-Path $PSScriptRoot 'server.py') + '"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log')
  for ($taskAttempt = 0; $taskAttempt -lt 25; $taskAttempt++) {
    Start-Sleep -Milliseconds 200
    try { $taskResult = Invoke-RestMethod -Uri ($taskUrl + 'api/catalog') -TimeoutSec 2; $taskRunning = $taskResult.schemaVersion -eq 1; if ($taskRunning) { break } } catch {}
  }
}
if ($taskRunning) { Start-Process $taskUrl } else { Write-Host '启动未完成，请查看 server-error.log'; Read-Host '按回车关闭' }
