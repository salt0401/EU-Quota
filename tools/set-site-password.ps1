# set-site-password.ps1
#
# One-time setup: store the Basic-auth password for the internal quota tracker
# site, on the company server, with the right encoding and permissions.
#
# Run this INTERACTIVELY over RDP or SSH. It prompts, so the password never
# appears in a command line, a shell history, a script, or a transcript.
#
#   powershell -ExecutionPolicy Bypass -File C:\DataScienceProject\EUQuota\tools\set-site-password.ps1
#
# This mirrors set-github-token.ps1 deliberately: same secrets folder, same
# ACL model, same BOM trap. Windows PowerShell 5.1 writes a UTF-8 BOM from both
# Set-Content and Out-File, and webapp/app.py reads the file with
# encoding="utf-8" -- a BOM would become part of the password and every login
# would fail with no useful message. This uses .NET directly to avoid it.
#
# Unlike the GitHub token, a trailing newline here is harmless (app.py calls
# .strip()), but it is stripped anyway so the stored bytes are exactly the
# password.
#
# NOTE: the site reads this file at STARTUP, not per request. Restart the
# waitress process after changing it.
#
# Pure ASCII by design.

param(
    [string]$PasswordFile = "C:\DataScienceProject\_secrets\quota-site-password.txt"
)

$ErrorActionPreference = "Stop"

$dir = Split-Path $PasswordFile -Parent
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    "Created $dir"
}

if (Test-Path $PasswordFile) {
    ""
    "WARNING: $PasswordFile already exists."
    "Continuing will REPLACE it, and everyone using the old password is locked out."
    $answer = Read-Host "Type 'replace' to continue, anything else to abort"
    if ($answer -ne "replace") { "Aborted. Nothing changed."; exit 1 }
}

""
"Set the shared password for the internal quota tracker site."
"It is typed by researchers into a browser prompt, so favour something"
"long and typeable over something short and cryptic."
"Input is hidden; you will be asked twice."
""

$secure1 = Read-Host -AsSecureString "Password"
$secure2 = Read-Host -AsSecureString "Confirm"

function ConvertFrom-Secure([System.Security.SecureString]$s) {
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$p1 = (ConvertFrom-Secure $secure1).Trim()
$p2 = (ConvertFrom-Secure $secure2).Trim()

if (-not $p1)    { throw "No password entered." }
if ($p1 -ne $p2) { throw "The two entries do not match. Nothing was written." }
if ($p1.Length -lt 12) {
    throw "Too short ($($p1.Length) chars). Use at least 12 -- this sits on a public-facing port."
}

# UTF-8 with NO BOM, no trailing newline.
[System.IO.File]::WriteAllText($PasswordFile, $p1, (New-Object System.Text.UTF8Encoding($false)))

# Readable only by the account serving the site, plus admins.
# /inheritance:r drops inherited grants first, or Users would still read it.
& icacls.exe $PasswordFile /inheritance:r /grant "SYSTEM:R" /grant "Administrators:F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls failed with exit code $LASTEXITCODE" }

# Verify what landed WITHOUT printing the password.
$bytes = [System.IO.File]::ReadAllBytes($PasswordFile)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$endsClean = ($bytes[$bytes.Length - 1] -ne 10 -and $bytes[$bytes.Length - 1] -ne 13)
$sha = (Get-FileHash -Path $PasswordFile -Algorithm SHA256).Hash.Substring(0, 12)

""
"Stored: $PasswordFile"
"  bytes           : $($bytes.Length)"
"  BOM             : $hasBom   (must be False)"
"  ends cleanly    : $endsClean   (must be True)"
"  sha256 prefix   : $sha   (fingerprint only; safe to quote when confirming)"
""
"Permissions:"
& icacls.exe $PasswordFile | ForEach-Object { "  $_" }
""
if ($hasBom -or -not $endsClean) {
    throw "The password file is malformed. Re-run this script."
}
"Password stored. The site will require Basic auth on its next start."
"/healthz stays open by design, so a monitor does not need the password."
