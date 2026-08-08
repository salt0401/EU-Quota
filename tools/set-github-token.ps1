# set-github-token.ps1
#
# One-time setup: store the GitHub push token the daily task uses, on the
# company server, with the right encoding and the right permissions.
#
# Run this INTERACTIVELY over SSH or RDP. It prompts for the token, so the
# token never appears in a command line, a shell history, a script, or a
# transcript.
#
#   ssh <server>   (details: C:\DataScienceProject\_secrets\server-access.md)
#   powershell -ExecutionPolicy Bypass -File C:\DataScienceProject\EUQuota\tools\set-github-token.ps1
#
# Two encoding details that are easy to get wrong and fail confusingly:
#
#   * NO BOM. git-askpass.cmd emits the file with `type`, so a UTF-8 BOM would
#     be prepended to the token and GitHub would reject it as a bad credential.
#     Set-Content and Out-File both write a BOM by default in Windows
#     PowerShell 5.1, so this uses .NET directly. (The same trap makes sshd
#     silently reject every key in administrators_authorized_keys -- see
#     meps-server-docs/docs/08-openssh-deployment-channel.md.)
#   * NO trailing newline. Written with WriteAllText, not WriteAllLines.
#
# Pure ASCII by design.

param(
    [string]$TokenFile = "C:\DataScienceProject\_secrets\euquota-github.token"
)

$ErrorActionPreference = "Stop"

$dir = Split-Path $TokenFile -Parent
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    "Created $dir"
}

""
"Paste the fine-grained GitHub token (scoped to salt0401/EU-Quota,"
"Repository permissions -> Contents: Read and write), then press Enter."
"Input is hidden."
""
$secure = Read-Host -AsSecureString "Token"
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $token = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $token) { throw "No token entered." }
if ($token.Length -lt 20) { throw "That does not look like a GitHub token (too short)." }

# UTF-8 with NO BOM, and no trailing newline.
[System.IO.File]::WriteAllText($TokenFile, $token, (New-Object System.Text.UTF8Encoding($false)))

# Readable only by the account the scheduled task runs as, plus admins.
# /inheritance:r drops the inherited grants first, or Users would still read it.
& icacls.exe $TokenFile /inheritance:r /grant "SYSTEM:R" /grant "Administrators:F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls failed with exit code $LASTEXITCODE" }

# Verify what landed WITHOUT printing the token.
$bytes = [System.IO.File]::ReadAllBytes($TokenFile)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$endsClean = ($bytes[$bytes.Length - 1] -ne 10 -and $bytes[$bytes.Length - 1] -ne 13)
$sha = (Get-FileHash -Path $TokenFile -Algorithm SHA256).Hash.Substring(0, 12)

""
"Stored: $TokenFile"
"  bytes           : $($bytes.Length)"
"  BOM             : $hasBom   (must be False)"
"  ends cleanly    : $endsClean   (must be True - no trailing newline)"
"  sha256 prefix   : $sha   (fingerprint only; safe to quote when confirming)"
""
"Permissions:"
& icacls.exe $TokenFile | ForEach-Object { "  $_" }
""
if ($hasBom -or -not $endsClean) {
    throw "The token file is malformed. Re-run this script."
}
"Token stored correctly. Next: verify the push path, then register the task."
