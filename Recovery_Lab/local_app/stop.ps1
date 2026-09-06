$ErrorActionPreference='Stop'
$sessionFile=Join-Path $PSScriptRoot 'runtime/session.json'
if(-not(Test-Path -LiteralPath $sessionFile)) {throw 'No process started by start.ps1 is recorded.'}
$session=Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
$targetProcess=Get-Process -Id ([int]$session.process_id) -ErrorAction SilentlyContinue
if(-not $targetProcess) {Write-Output 'Recovery Lab is already stopped.';exit}
$expectedFolder=Join-Path $PSScriptRoot 'api'
if($targetProcess.StartTime.ToUniversalTime().Ticks -ne ([datetime]$session.started_utc).ToUniversalTime().Ticks -or $session.app_folder -ne $expectedFolder -or ($session.executable_path -and $targetProcess.Path -ne $session.executable_path) -or (-not $session.executable_path -and $targetProcess.ProcessName -ne 'python')) {
    throw 'The process identity differs from the recorded Recovery Lab process. Nothing was stopped.'
}
Stop-Process -Id $targetProcess.Id
Write-Output 'Recovery Lab stopped. The audit journal remains in runtime/.'
