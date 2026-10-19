$ErrorActionPreference = 'Stop'
$dapRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dapStatePath = Join-Path $dapRoot '.local/workspace/services.json'
if (-not (Test-Path -LiteralPath $dapStatePath)) { Write-Output 'No recorded workspace services.'; return }
$dapState = Get-Content -LiteralPath $dapStatePath -Raw | ConvertFrom-Json
if ($dapState.root -ne $dapRoot) { throw 'Recorded workspace root differs.' }
foreach ($dapKind in @('worker','frontend','backend')) {
    $dapPid = [int]$dapState."${dapKind}_pid"
    if (-not $dapPid) { continue }
    $dapProcess = Get-Process -Id $dapPid -ErrorAction SilentlyContinue
    if (-not $dapProcess) { continue }
    $dapExpectedTime = ([datetime]$dapState."${dapKind}_started").ToUniversalTime()
    if ([Math]::Abs(($dapProcess.StartTime.ToUniversalTime()-$dapExpectedTime).TotalSeconds) -gt 1) { throw "Recorded $dapKind PID was reused; refusing to stop it." }
    $dapCommandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$dapPid").CommandLine
    if (-not $dapCommandLine.Contains($dapRoot) -or -not ($dapCommandLine.Contains('workspace_command.py') -or $dapCommandLine.Contains('vite.js'))) { throw 'Recorded process does not belong to the workspace launcher.' }
    & taskkill.exe /PID $dapPid /T /F
    if ($LASTEXITCODE -ne 0) { throw "Stopping $dapKind failed." }
}
Write-Output 'Recorded V3 workspace services stopped; database and V1/V2 services retained.'
