$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.buildenv\Scripts\python.exe')) {
    python -m venv .buildenv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ x64 is required to build.' }
}
& .\.buildenv\Scripts\python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .\.buildenv\Scripts\python.exe -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& .\.buildenv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name GPUChecker-v3 --icon assets/app.ico --add-data 'src/remote_probe.py;.' --add-data 'assets/app.ico;assets' --add-data 'assets/fonts;assets/fonts' --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module tkinter --distpath delivery src/app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
& .\.buildenv\Scripts\python.exe package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
Get-FileHash -LiteralPath delivery\GPUChecker-v3.exe -Algorithm SHA256
