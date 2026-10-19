param([ValidateSet('dev','test')][string]$Target = 'dev', [switch]$WithWorker)
$ErrorActionPreference = 'Stop'
$dapRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dapPrivate = Join-Path $dapRoot '.local/workspace'
$dapConfig = Join-Path $dapPrivate 'environment.json'
if (-not (Test-Path -LiteralPath $dapConfig)) { throw 'Run backend/scripts/prepare_workspace.py first.' }
foreach ($dapPort in @(8305,5175)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $dapPort -ErrorAction SilentlyContinue) { throw "Workspace port $dapPort is already occupied; inspect it before restarting." }
}
$dapPython = Join-Path $dapRoot 'backend/.venv/Scripts/python.exe'
$dapNode = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $dapNode) { $dapNode = 'D:/Dev/Node.js/node.exe' }
if (-not (Test-Path -LiteralPath $dapNode)) { throw 'Node.js is unavailable.' }
$dapBackendArgs = @('"'+(Join-Path $dapRoot 'backend/scripts/workspace_command.py')+'"', $Target, 'python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8305', '--no-access-log')
$dapBackend = Start-Process -FilePath $dapPython -ArgumentList $dapBackendArgs -WorkingDirectory (Join-Path $dapRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dapPrivate 'backend.stdout.log') -RedirectStandardError (Join-Path $dapPrivate 'backend.stderr.log')
$dapOldEnv = @{}
$dapFrontEnv = @{VITE_API_BASE_URL='/api/v1'; VITE_API_PROXY_TARGET='http://127.0.0.1:8305'; VITE_TEST_SUBJECT=$null; VITE_TEST_CAPABILITIES=$null}
try {
    foreach ($dapKey in $dapFrontEnv.Keys) { $dapOldEnv[$dapKey]=[Environment]::GetEnvironmentVariable($dapKey,'Process'); [Environment]::SetEnvironmentVariable($dapKey,$dapFrontEnv[$dapKey],'Process') }
    $dapFrontArgs = @('"'+(Join-Path $dapRoot 'frontend/node_modules/vite/bin/vite.js')+'"', '--host', '127.0.0.1', '--port', '5175', '--strictPort')
    $dapFrontend = Start-Process -FilePath $dapNode -ArgumentList $dapFrontArgs -WorkingDirectory (Join-Path $dapRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dapPrivate 'frontend.stdout.log') -RedirectStandardError (Join-Path $dapPrivate 'frontend.stderr.log')
} finally {
    foreach ($dapKey in $dapFrontEnv.Keys) { [Environment]::SetEnvironmentVariable($dapKey,$dapOldEnv[$dapKey],'Process') }
}
$dapState = @{root=$dapRoot; target=$Target; backend_pid=$dapBackend.Id; frontend_pid=$dapFrontend.Id; backend_started=$dapBackend.StartTime.ToUniversalTime().ToString('o'); frontend_started=$dapFrontend.StartTime.ToUniversalTime().ToString('o'); backend='http://127.0.0.1:8305'; frontend='http://127.0.0.1:5175'}
if ($WithWorker) {
    $dapWorkerArgs = @('"'+(Join-Path $dapRoot 'backend/scripts/workspace_command.py')+'"', $Target, 'python', '-m', 'app.worker')
    $dapWorker = Start-Process -FilePath $dapPython -ArgumentList $dapWorkerArgs -WorkingDirectory (Join-Path $dapRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dapPrivate 'worker.stdout.log') -RedirectStandardError (Join-Path $dapPrivate 'worker.stderr.log')
    $dapState.worker_pid=$dapWorker.Id; $dapState.worker_started=$dapWorker.StartTime.ToUniversalTime().ToString('o')
}
$dapState | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dapPrivate 'services.json') -Encoding utf8
$dapState | Select-Object target,frontend,backend | ConvertTo-Json
Write-Output 'Logs and process IDs: .local/workspace. No migration runs during startup.'
