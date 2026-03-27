$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pythonCandidates = @(
    (Join-Path $root ".venv\\Scripts\\python.exe"),
    (Join-Path $root ".venv\\python.exe")
)

$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $python) {
    $expected = $pythonCandidates -join ", "
    throw "Virtual environment not found. Expected one of: $expected"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name R6TacticsBoard `
    --paths src `
    --add-data "src/assets;assets" `
    --collect-all qfluentwidgets `
    --collect-all qframelesswindow `
    src/r6_tactics_board/__main__.py
