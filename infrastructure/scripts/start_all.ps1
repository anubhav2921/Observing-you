# PowerShell unified launcher for AI Study Focus Monitor
param(
    [string]$Mode = "web",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AI Study Focus Monitor (Mode: $Mode)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
    $PythonExe = "$RepoRoot\.venv\Scripts\python.exe"
} else {
    $PythonExe = "python"
}

& $PythonExe "$RepoRoot\run_app.py" --mode $Mode --host $Host --port $Port

