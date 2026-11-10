param(
    [Parameter(Mandatory=$true)][string]$RuntimeDirectory,
    [string]$CertificateThumbprint = $env:GPUCHECKER_SIGNING_THUMBPRINT,
    [string]$SignToolPath,
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [switch]$VerifyOnly,
    [switch]$DevelopmentUnsigned,
    [switch]$Preflight
)
$ErrorActionPreference = 'Stop'

if (-not $DevelopmentUnsigned -and -not $VerifyOnly) {
    if (-not $CertificateThumbprint) {
        throw 'A trusted publisher certificate is required. Set GPUCHECKER_SIGNING_THUMBPRINT, or explicitly use -DevelopmentUnsigned for a local test build. Unsigned builds may be blocked by Smart App Control.'
    }
    $CertificateThumbprint = $CertificateThumbprint.Replace(' ', '')
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
    if (-not $certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date) -or $certificate.NotBefore -gt (Get-Date)) {
        throw 'The selected certificate has no private key or is outside its validity period.'
    }
    if ($certificate.Subject -eq $certificate.Issuer) { throw 'A self-signed publisher certificate is not accepted for public distribution.' }
    $usages = @($certificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | ForEach-Object { $_.EnhancedKeyUsages } | ForEach-Object { $_.Value })
    if ('1.3.6.1.5.5.7.3.3' -notin $usages) {
        throw 'The selected certificate is not a code-signing certificate.'
    }
    if (-not $SignToolPath) {
        $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($command) { $SignToolPath = $command.Source }
        else {
            $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
            $candidate = Get-ChildItem -LiteralPath $kits -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
                Where-Object FullName -Match '\\x64\\' | Sort-Object FullName -Descending | Select-Object -First 1
            if ($candidate) { $SignToolPath = $candidate.FullName }
        }
    }
    if (-not $SignToolPath -or -not (Test-Path -LiteralPath $SignToolPath)) { throw 'Install the Windows SDK SignTool, or supply -SignToolPath.' }
}
if ($Preflight) { return }

$runtime = (Resolve-Path -LiteralPath $RuntimeDirectory).Path
$main = Join-Path $runtime 'GPUChecker.exe'
if (-not (Test-Path -LiteralPath $main)) { throw 'GPUChecker.exe is missing from the runtime directory.' }
$files = @(Get-ChildItem -LiteralPath $runtime -Recurse -File | Where-Object { $_.Extension.ToLowerInvariant() -in '.exe','.dll','.pyd' })
$report = @()
foreach ($file in $files) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if (-not $DevelopmentUnsigned) {
        if (-not $VerifyOnly -and ($file.FullName -eq $main -or $signature.Status -eq 'NotSigned')) {
            & $SignToolPath sign /sha1 $CertificateThumbprint /s My /fd SHA256 /tr $TimestampUrl /td SHA256 /d 'GPU Checker' $file.FullName
            if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.Name)" }
            $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
        }
        if ($signature.Status -ne 'Valid') { throw "Untrusted or missing binary signature: $($file.Name) ($($signature.Status)). No release package was produced." }
        if ($signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer) { throw "Self-signed binary: $($file.Name)" }
        if ($file.FullName -eq $main -and -not $signature.TimeStamperCertificate) { throw 'The publisher signature needs a trusted timestamp.' }
    }
    $relative = $file.FullName.Substring($runtime.Length).TrimStart('\','/').Replace('\','/')
    $report += [ordered]@{
        file = $relative
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        status = $signature.Status.ToString()
        subject = $(if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null })
    }
}
$record = [ordered]@{
    schema = 1
    distribution = $(if ($DevelopmentUnsigned) { 'unsigned-development' } else { 'signed-release' })
    note = 'Signature verification is on the build machine. Smart App Control must also be tested on a protected clean Windows device; hashes alone do not establish publisher trust.'
    binaries = $report
}
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runtime 'SIGNATURES.json') -Encoding UTF8
Write-Output "Checked $($files.Count) binary signatures ($($record.distribution))."
