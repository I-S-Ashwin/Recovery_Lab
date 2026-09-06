param([string]$PythonExecutable='')
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$runtime=Join-Path $projectRoot 'runtime'
if(Get-NetTCPConnection -State Listen -LocalPort 8078 -ErrorAction SilentlyContinue) {
    throw 'Port 8078 is already in use. Open http://127.0.0.1:8078/ if Recovery Lab is running; otherwise stop the conflicting service first.'
}
if(-not(Test-Path -LiteralPath (Join-Path $projectRoot 'dashboard/dist/client/index.html'))) {throw 'The dashboard build is missing.'}
if(-not $PythonExecutable) {
    $venv=Join-Path $projectRoot '.venv/Scripts/python.exe'
    if(Test-Path -LiteralPath $venv) {$PythonExecutable=$venv}
    else {$PythonExecutable=(Get-Command python -ErrorAction Stop).Source}
}
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$env:TVS_RUNTIME_DIR=$runtime
$env:PYTHONUTF8='1'
$appFolder=Join-Path $projectRoot 'api'
$arguments=@('-m','uvicorn','service:app','--app-dir',('"'+$appFolder+'"'),'--host','127.0.0.1','--port','8078','--no-access-log','--no-proxy-headers')
$process=Start-Process -FilePath $PythonExecutable -WorkingDirectory $projectRoot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'service.log') -RedirectStandardError (Join-Path $runtime 'service-errors.log')
@{process_id=$process.Id;app_folder=$appFolder;executable_path=$process.Path;started_utc=$process.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'session.json')
$ready=$false
for($attempt=0;$attempt -lt 30;$attempt++) {
    if($process.HasExited) {throw 'Service startup failed. See runtime/service-errors.log.'}
    try { $response=Invoke-RestMethod -Uri 'http://127.0.0.1:8078/ready' -TimeoutSec 1; if($response.status -eq 'ready') {$ready=$true;break} } catch {}
    Start-Sleep -Milliseconds 500
}
if(-not $ready) {throw 'Startup is still pending. Check runtime/service-errors.log and the readiness URL before retrying.'}
Write-Output 'Recovery Lab is ready at http://127.0.0.1:8078/ . Use stop.ps1 to stop this service.'
