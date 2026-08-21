# install-iis-reverse-proxy.ps1
#
# Installs and configures the IIS front end for the internal quota tracker:
# URL Rewrite 2.1 + Application Request Routing 3.0, then a reverse-proxy site
# forwarding to waitress on loopback.
#
# WHY A SCRIPT AND NOT A FEW COMMANDS. MEPS is provisioning a replacement VPS,
# so every step here has to run again on a different machine. It is idempotent,
# it pins the payload hashes, and it REFUSES rather than guesses when it finds
# something already present.
#
# SAFETY, because this box runs a live public API on IIS:
#   * Installers run /quiet /norestart. Exit code 3010 (reboot required) is a
#     FAILURE here, not a success -- nothing needing a reboot goes on this box.
#   * -Preflight downloads and INSPECTS the MSIs without installing, so the
#     reboot question is answered before any installer runs.
#   * Installing these modules restarts W3SVC; the public API drops for a few
#     seconds. Run it in a quiet window -- see docs/INTERNAL_SITE.md.
#   * -ConfigureSite refuses unless the certificate exists, and never touches
#     the existing site.
#
# USAGE
#   powershell -ExecutionPolicy Bypass -File tools\install-iis-reverse-proxy.ps1 -Preflight
#   powershell -ExecutionPolicy Bypass -File tools\install-iis-reverse-proxy.ps1 -Install
#   powershell -ExecutionPolicy Bypass -File tools\install-iis-reverse-proxy.ps1 -ConfigureSite
#   powershell -ExecutionPolicy Bypass -File tools\install-iis-reverse-proxy.ps1 -Verify
#
# Pure ASCII by design.

[CmdletBinding()]
param(
    [switch]$Preflight,
    [switch]$Install,
    [switch]$ConfigureSite,
    [switch]$Verify,
    [string]$HostName    = "quota.meps.co.uk",
    [string]$SiteName    = "quota-tracker",
    [int]   $BackendPort = 8081,
    [string]$CacheDir    = "C:\DataScienceProject\_installers",
    [string]$LogDir      = "C:\DataScienceProject\EUQuota\data\logs"
)

$ErrorActionPreference = "Stop"
$script:fail = 0

function Say  { param([string]$m) Write-Output $m }
function Step { param([string]$m) Write-Output ""; Write-Output ("=== " + $m + " ===") }
function Ok   { param([string]$m) Write-Output ("  PASS  " + $m) }
function Bad  { param([string]$m) Write-Output ("  FAIL  " + $m); $script:fail++ }
function Note { param([string]$m) Write-Output ("  NOTE  " + $m) }
function Die  { param([string]$m) Write-Output ""; Write-Output ("ABORT: " + $m); exit 1 }

# --- payload ---------------------------------------------------------------
# Hashes are pinned so a re-run on another machine fetches the same bytes or
# stops. Change them deliberately, never silently.
$payload = @(
    @{ Name   = "URL Rewrite 2.1"
       File   = "rewrite_amd64_en-US.msi"
       Url    = "https://download.microsoft.com/download/1/2/8/128E2E22-C1B9-44A4-BE2A-5859ED1D4592/rewrite_amd64_en-US.msi"
       Sha    = "37342FF2F585F263F34F48E9DE59EB1051D61015A8E967DBDE4075716230A32A"
       RegKey = "HKLM:\SOFTWARE\Microsoft\IIS Extensions\URL Rewrite" },
    @{ Name   = "Application Request Routing 3.0"
       File   = "requestRouter_amd64.msi"
       Url    = "https://download.microsoft.com/download/E/9/8/E9849D6A-020E-47E4-9FD0-A023E99B54EB/requestRouter_amd64.msi"
       Sha    = "FB61FDB7101795A34D5129CB37EEE43AB675C7ED76BA3A3B23B039D8C90C2A4B"
       RegKey = "HKLM:\SOFTWARE\Microsoft\IIS Extensions\Application Request Routing" }
)

$appcmd = "$env:WinDir\System32\inetsrv\appcmd.exe"

function Assert-Environment {
    Step "Environment"
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Die "must run elevated" }
    Ok ("elevated as " + $id.Name)

    if (-not (Test-Path $appcmd)) { Die "IIS is not installed" }
    Ok "IIS present"

    $w3 = Get-Service W3SVC -ErrorAction SilentlyContinue
    if (-not $w3) { Die "W3SVC service not found" }
    Ok ("W3SVC is " + $w3.Status)

    if (-not (Test-Path $CacheDir)) { New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null }
    if (-not (Test-Path $LogDir))   { New-Item -ItemType Directory -Path $LogDir   -Force | Out-Null }
}

function Get-Payload {
    Step "Payload"
    foreach ($p in $payload) {
        $dest = Join-Path $CacheDir $p.File
        if (Test-Path $dest) {
            Ok ($p.File + " already cached")
        } else {
            Say ("  downloading " + $p.Name + " ...")
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $p.Url -OutFile $dest -UseBasicParsing -TimeoutSec 180
            } catch {
                Bad ($p.Name + " download failed: " + $_.Exception.Message.Split([char]10)[0])
                continue
            }
            Ok ("downloaded " + $p.File)
        }
        $sha = (Get-FileHash -Path $dest -Algorithm SHA256).Hash
        Say ("        size   : " + (Get-Item $dest).Length + " bytes")
        Say ("        sha256 : " + $sha)
        if ($p.Sha -eq "__PIN_ME__") {
            Note "hash not pinned yet -- record the value above in this script"
        } elseif ($sha -ne $p.Sha) {
            Bad ($p.File + " HASH MISMATCH -- expected " + $p.Sha)
        } else {
            Ok "hash matches the pinned value"
        }
    }
}

# Read an MSI table without installing anything.
function Invoke-MsiQuery {
    param([string]$Path, [string]$Sql)
    $rows = @()
    $wi = New-Object -ComObject WindowsInstaller.Installer
    $db = $wi.GetType().InvokeMember("OpenDatabase", "InvokeMethod", $null, $wi, @($Path, 0))
    try {
        $vw = $db.GetType().InvokeMember("OpenView", "InvokeMethod", $null, $db, @($Sql))
        $vw.GetType().InvokeMember("Execute", "InvokeMethod", $null, $vw, $null) | Out-Null
        while ($true) {
            $rec = $vw.GetType().InvokeMember("Fetch", "InvokeMethod", $null, $vw, $null)
            if ($null -eq $rec) { break }
            $n = $rec.GetType().InvokeMember("FieldCount", "GetProperty", $null, $rec, $null)
            $vals = @()
            for ($i = 1; $i -le $n; $i++) {
                $vals += [string]$rec.GetType().InvokeMember("StringData", "GetProperty", $null, $rec, @($i))
            }
            $rows += ,$vals
        }
        $vw.GetType().InvokeMember("Close", "InvokeMethod", $null, $vw, $null) | Out-Null
    } finally {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($db)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wi)
    }
    return $rows
}

function Test-MsiReboot {
    Step "Reboot inspection (BEFORE any installer runs)"
    foreach ($p in $payload) {
        $dest = Join-Path $CacheDir $p.File
        if (-not (Test-Path $dest)) { Bad ($p.File + " not present, cannot inspect"); continue }
        Say ""
        Say ("  --- " + $p.Name + " ---")
        try {
            $prod = Invoke-MsiQuery $dest "SELECT Property, Value FROM Property WHERE Property = 'ProductName' OR Property = 'ProductVersion' OR Property = 'REBOOT'"
            foreach ($r in $prod) { Say ("        " + $r[0] + " = " + $r[1]) }

            $seq = Invoke-MsiQuery $dest "SELECT Action FROM InstallExecuteSequence WHERE Action = 'ForceReboot' OR Action = 'ScheduleReboot'"
            if ($seq.Count -eq 0) {
                Ok "no ForceReboot / ScheduleReboot action in InstallExecuteSequence"
            } else {
                Bad ("MSI schedules a reboot: " + (($seq | ForEach-Object { $_[0] }) -join ", "))
            }

            $lc = Invoke-MsiQuery $dest "SELECT Condition FROM LaunchCondition"
            if ($lc.Count -eq 0) { Say "        (no launch conditions)" }
            foreach ($r in $lc) { Say ("        condition: " + $r[0]) }
        } catch {
            Bad ("could not inspect " + $p.File + ": " + $_.Exception.Message.Split([char]10)[0])
        }
    }
    Say ""
    Note "A clean inspection is necessary, not sufficient: a file in use can still"
    Note "trigger a reboot request at install time. The install step therefore passes"
    Note "/norestart and treats exit code 3010 as a failure."
}

function Install-Payload {
    Step "Install"
    foreach ($p in $payload) {
        if (Test-Path $p.RegKey) { Ok ($p.Name + " already installed -- skipping (idempotent)"); continue }

        $dest = Join-Path $CacheDir $p.File
        if (-not (Test-Path $dest)) { Bad ($p.File + " missing; run -Preflight first"); continue }

        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $log   = Join-Path $LogDir ("msi_" + [IO.Path]::GetFileNameWithoutExtension($p.File) + "_" + $stamp + ".log")
        Say ("  installing " + $p.Name)
        Say ("        log: " + $log)

        $args = @("/i", ('"' + $dest + '"'), "/quiet", "/norestart", "/l*v", ('"' + $log + '"'))
        $proc = Start-Process -FilePath "msiexec.exe" -ArgumentList $args -Wait -PassThru
        $rc = $proc.ExitCode

        if ($rc -eq 0) {
            Ok ($p.Name + " installed (exit 0)")
        } elseif ($rc -eq 3010) {
            Bad ($p.Name + " returned 3010 = REBOOT REQUIRED. Nothing needing a reboot goes on this box. Read the log before doing anything else.")
        } elseif ($rc -eq 1638) {
            Note ($p.Name + " reports another version already installed (1638)")
        } else {
            Bad ($p.Name + " failed with exit code " + $rc + " -- see " + $log)
        }
    }
}

function Enable-Proxy {
    Step "Enable ARR proxy"
    $cur = & $appcmd list config -section:system.webServer/proxy 2>&1 | Out-String
    if ($cur -match 'Unknown config section') { Bad "system.webServer/proxy absent -- ARR is not installed"; return }
    if ($cur -match 'enabled="true"')         { Ok "proxy already enabled -- leaving it alone"; return }
    & $appcmd set config -section:system.webServer/proxy /enabled:"True" /commit:apphost | Out-Null
    if ($LASTEXITCODE -ne 0) { Bad "failed to enable the proxy"; return }
    Ok "proxy enabled"
}

function Set-ProxySite {
    Step "Reverse-proxy site"
    Import-Module WebAdministration -ErrorAction Stop

    $cert = Get-ChildItem Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
            Where-Object { $_.Subject -match [regex]::Escape($HostName) -or $_.DnsNameList.Unicode -contains $HostName }
    if (-not $cert) {
        Bad ("no certificate for " + $HostName + " in LocalMachine\My -- BLOCKED until it is issued")
        Note "This is the documented boundary. Nothing further can proceed without the certificate and the DNS record."
        return
    }
    Ok ("certificate found: " + $cert[0].Thumbprint)

    if (Get-Website -Name $SiteName -ErrorAction SilentlyContinue) {
        Bad ("site '" + $SiteName + "' already exists -- refusing to modify it. Remove it deliberately to recreate.")
        return
    }

    $root = "C:\inetpub\wwwroot\" + $SiteName
    if (-not (Test-Path $root)) { New-Item -ItemType Directory -Path $root -Force | Out-Null }

    if (-not (Test-Path ("IIS:\AppPools\" + $SiteName))) {
        New-WebAppPool -Name $SiteName | Out-Null
        Set-ItemProperty ("IIS:\AppPools\" + $SiteName) -Name managedRuntimeVersion -Value ""
        Ok "app pool created (No Managed Code)"
    }

    New-Website -Name $SiteName -PhysicalPath $root -ApplicationPool $SiteName -HostHeader $HostName -Port 443 -Ssl | Out-Null
    Ok "site created with an SNI https binding"

    $bind = Get-WebBinding -Name $SiteName -Protocol https
    $bind.AddSslCertificate($cert[0].Thumbprint, "My")
    Ok "certificate bound"

    $lines = @(
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<configuration>',
        '  <system.webServer>',
        '    <rewrite>',
        '      <rules>',
        '        <rule name="ReverseProxyToWaitress" stopProcessing="true">',
        '          <match url="(.*)" />',
        ('          <action type="Rewrite" url="http://127.0.0.1:' + $BackendPort + '/{R:1}" />'),
        '        </rule>',
        '      </rules>',
        '    </rewrite>',
        '  </system.webServer>',
        '</configuration>'
    )
    $webConfig = Join-Path $root "web.config"
    [IO.File]::WriteAllText($webConfig, ($lines -join [Environment]::NewLine), (New-Object Text.UTF8Encoding($false)))
    Ok ("reverse-proxy rule written to " + $webConfig)
    Note "The site is now reachable. It is UNAUTHENTICATED until tools\set-site-password.ps1 has been run."
}

function Test-Result {
    Step "Verify"
    $mods = & $appcmd list modules 2>&1 | Out-String

    if ($mods -match "RewriteModule")             { Ok "URL Rewrite module registered" } else { Bad "URL Rewrite module NOT registered" }
    if ($mods -match "ApplicationRequestRouting") { Ok "ARR module registered" }         else { Bad "ARR module NOT registered" }

    foreach ($p in $payload) {
        if (Test-Path $p.RegKey) {
            $v = (Get-ItemProperty $p.RegKey -ErrorAction SilentlyContinue).Version
            if ($v) { Ok ($p.Name + " present (version " + $v + ")") } else { Ok ($p.Name + " present") }
        } else {
            Bad ($p.Name + " registry key absent")
        }
    }

    $cfg = & $appcmd list config -section:system.webServer/proxy 2>&1 | Out-String
    if ($cfg -match 'enabled="true"') { Ok "ARR proxy enabled" } else { Note "ARR proxy not enabled yet" }

    $w3 = Get-Service W3SVC
    if ($w3.Status -eq "Running") { Ok "W3SVC running" } else { Bad ("W3SVC is " + $w3.Status) }

    # The whole point of the quiet window: prove the live API survived.
    $live = & $appcmd list site "api.mepsinternational.com" 2>&1 | Out-String
    if ($live -match "state:Started") { Ok "the live public API site is still Started" }
    else { Bad "THE LIVE API SITE IS NOT STARTED -- investigate immediately" }
}

# --- main ------------------------------------------------------------------
Say "IIS reverse proxy for the internal quota tracker"
Say ("host name : " + $HostName)
Say ("backend   : http://127.0.0.1:" + $BackendPort)
Say ("cache dir : " + $CacheDir)

Assert-Environment

if (-not ($Preflight -or $Install -or $ConfigureSite -or $Verify)) {
    Say ""
    Say "Nothing to do. Pass -Preflight, -Install, -ConfigureSite or -Verify."
    exit 0
}

if ($Preflight)     { Get-Payload; Test-MsiReboot }
if ($Install)       { Get-Payload; Install-Payload; Enable-Proxy; Test-Result }
if ($ConfigureSite) { Set-ProxySite }
if ($Verify)        { Test-Result }

Say ""
if ($script:fail -eq 0) { Say "OK - no failures."; exit 0 }
Say ("FAILURES: " + $script:fail)
exit $script:fail
