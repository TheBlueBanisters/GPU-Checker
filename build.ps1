param(
    [switch]$DevelopmentUnsigned,
    [string]$CertificateThumbprint = $env:GPUCHECKER_SIGNING_THUMBPRINT,
    [string]$SignToolPath,
    [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$signing = @{ RuntimeDirectory = 'build/release-runtime/GPUChecker'; DevelopmentUnsigned = $DevelopmentUnsigned }
if ($CertificateThumbprint) { $signing.CertificateThumbprint = $CertificateThumbprint }
if ($SignToolPath) { $signing.SignToolPath = $SignToolPath }
& "$PSScriptRoot/sign_windows.ps1" @signing -Preflight
if (-not (Test-Path -LiteralPath '.buildenv\Scripts\python.exe')) {
    python -m venv .buildenv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ x64 is required to build.' }
}
& .\.buildenv\Scripts\python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not $SkipTests) {
    & .\.buildenv\Scripts\python.exe -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
}
# A directory runtime makes every loadable binary available for signing before ZIP packaging.
& .\.buildenv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --noupx --windowed --name GPUChecker --icon assets/app.ico --add-data 'src/remote_probe.py;.' --add-data 'assets/app.ico;assets' --add-data 'assets/fonts;assets/fonts' --add-data 'assets/audio;assets/audio' --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module tkinter --distpath build/release-runtime src/app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
& "$PSScriptRoot/sign_windows.ps1" @signing
$packaging = @('--runtime','build/release-runtime/GPUChecker')
if ($DevelopmentUnsigned) { $packaging += '--allow-unsigned-development' }
& .\.buildenv\Scripts\python.exe package_github_release.py @packaging
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
$releaseVersion = & .\.buildenv\Scripts\python.exe -c "import runpy; print(runpy.run_path('src/version.py')['APP_VERSION'])"
$outputBase = if ($DevelopmentUnsigned) { 'delivery\development' } else { 'delivery\releases' }
Get-ChildItem -LiteralPath "$outputBase\v$releaseVersion" -Filter *.zip | Get-FileHash -Algorithm SHA256
