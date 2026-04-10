$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run 'python -m venv .venv' and install dependencies first."
}

Push-Location $repoRoot
try {
    & $python -m ai_news_digest @args
}
finally {
    Pop-Location
}
