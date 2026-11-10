$ErrorActionPreference = "Stop"
$AlemRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalPython = Join-Path $AlemRoot ".alem\venv\Scripts\python.exe"
$BootstrapRequested = $args.Count -gt 1 -and $args[0] -eq "setup" -and $args -contains "--create-venv"
if ($BootstrapRequested) {
    $BootstrapPython = if (Test-Path -LiteralPath $LocalPython) { $LocalPython } else { "python" }
    & $BootstrapPython (Join-Path $AlemRoot "scripts\bootstrap_runtime.py") $AlemRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$AlemPython = if (Test-Path -LiteralPath $LocalPython) { $LocalPython } else { "python" }
$ExistingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
$env:PYTHONPATH = if ($ExistingPythonPath) { "$(Join-Path $AlemRoot 'src');$ExistingPythonPath" } else { Join-Path $AlemRoot "src" }
& $AlemPython -m alem @args
exit $LASTEXITCODE
