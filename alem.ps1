$ErrorActionPreference = "Stop"
$AlemRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalPython = Join-Path $AlemRoot ".alem\venv\Scripts\python.exe"
$AlemPython = if (Test-Path -LiteralPath $LocalPython) { $LocalPython } else { "python" }
$ExistingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
$env:PYTHONPATH = if ($ExistingPythonPath) { "$(Join-Path $AlemRoot 'src');$ExistingPythonPath" } else { Join-Path $AlemRoot "src" }
& $AlemPython -m alem @args
exit $LASTEXITCODE
