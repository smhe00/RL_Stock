param(
    [string]$ConfigPath = "config\local_reviewer.example.toml",
    [switch]$Once,
    [string]$RetryHandoff = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Watcher = Join-Path $RepoRoot "scripts\local_reviewer_watcher.py"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $Python = $PythonCommand.Source
}

$CodexCommand = Get-Command codex -ErrorAction Stop
if (-not $CodexCommand) {
    throw "codex is not available on PATH"
}

$RuntimeRoot = Join-Path $RepoRoot "runtime\local_reviewer"
New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "tmp") | Out-Null

$Arguments = @($Watcher, "--config", $ConfigPath)
if ($Once) {
    $Arguments += "--once"
}
if ($RetryHandoff) {
    $Arguments += @("--retry-handoff", $RetryHandoff)
}

Push-Location $RepoRoot
try {
    & $Python @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

