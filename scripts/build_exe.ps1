$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\\Scripts\\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found: $python"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name R6TacticsBoard `
    --paths src `
    --add-data "assets;assets" `
    --collect-all qfluentwidgets `
    --collect-all qframelesswindow `
    src/r6_tactics_board/__main__.py
