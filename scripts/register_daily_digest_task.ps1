$ErrorActionPreference = "Stop"

param(
    [string]$TaskName = "AI-Daily-Digest",
    [datetime]$At = (Get-Date "10:30"),
    [string]$Mode = "api",
    [string]$InputPath = "input\latest_digest.json",
    [string]$ConfigPath = "config\search_sources.json",
    [string]$StateDir = "state",
    [string]$OutputDir = "output",
    [switch]$WriteTopicReports
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $repoRoot "scripts\run_digest.ps1"

if (-not (Test-Path $runner)) {
    throw "Runner script not found: $runner"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$runner`"",
    "--mode", $Mode,
    "--input", $InputPath,
    "--config", $ConfigPath,
    "--state-dir", $StateDir,
    "--output-dir", $OutputDir
)

if ($WriteTopicReports) {
    $arguments += "--write-topic-reports"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($arguments -join " ")
$trigger = New-ScheduledTaskTrigger -Daily -At $At

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Description "Daily AI digest generation with optional topic reports" `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' at $($At.ToString('HH:mm'))."
