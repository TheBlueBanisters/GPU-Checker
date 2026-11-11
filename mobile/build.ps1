param([switch]$DebugBuild, [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22.12+ and npm 11+ first.' }
if (-not $env:JAVA_HOME) { throw 'Set JAVA_HOME to a JDK 21+ installation.' }
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
if (-not (Test-Path -LiteralPath (Join-Path $sdk 'platforms/android-36/android.jar'))) { throw 'Install Android SDK Platform 36 and Build Tools 36.0.0 through Android Studio SDK Manager.' }
$env:ANDROID_HOME = $sdk
if (-not $SkipInstall) {
    $npmVersion = (& npm.cmd --version).Trim()
    if ([int]($npmVersion.Split('.')[0]) -lt 11) {
        # Use a project-scoped npm; do not change the user's global installation.
        Invoke-Checked 'npx.cmd' @('--yes', 'npm@11.6.2', 'ci')
    } else { Invoke-Checked 'npm.cmd' @('ci') }
}
Invoke-Checked 'npm.cmd' @('run', 'build')
Invoke-Checked 'npx.cmd' @('cap', 'sync', 'android')
Invoke-Checked 'node' @('scripts/prepare-native.mjs')
$sdkProperty = -join ($sdk.Replace('\','/').ToCharArray() | ForEach-Object {
    if ([int]$_ -gt 127) { '\u{0:x4}' -f [int]$_ } else { [string]$_ }
})
('sdk.dir=' + $sdkProperty) | Set-Content -LiteralPath 'android/local.properties' -Encoding ascii
$variant = if ($DebugBuild) { 'debug' } else { 'release' }
$task = if ($DebugBuild) { ':app:assembleDebug' } else { ':app:assembleRelease' }
Invoke-Checked '.\android\gradlew.bat' @('-p', 'android', $task, '--console=plain', '--max-workers=3')
New-Item -ItemType Directory -Force 'delivery' | Out-Null
$output = Join-Path $PSScriptRoot "delivery/GPUChecker-Android-v1.0.14-$variant-test.apk"
Copy-Item -LiteralPath "android/app/build/outputs/apk/$variant/app-$variant.apk" -Destination $output -Force
Get-FileHash -LiteralPath $output -Algorithm SHA256
Write-Host "APK: $output"
