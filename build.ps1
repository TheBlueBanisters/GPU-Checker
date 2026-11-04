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
& .\.buildenv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name GPUChecker --icon assets/app.ico --add-data 'src/remote_probe.py;.' --add-data 'assets/app.ico;assets' --add-data 'assets/fonts;assets/fonts' --add-data 'assets/audio;assets/audio' --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module tkinter --distpath build/release-runtime src/app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
& .\.buildenv\Scripts\python.exe package_github_release.py --exe build/release-runtime/GPUChecker.exe
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
$releaseVersion = & .\.buildenv\Scripts\python.exe -c "import runpy; print(runpy.run_path('src/version.py')['APP_VERSION'])"
Get-FileHash -LiteralPath "delivery\releases\v$releaseVersion\GPUChecker.exe" -Algorithm SHA256
