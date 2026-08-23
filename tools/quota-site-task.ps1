# quota-site-task.ps1
#
# Keeps the internal quota tracker serving across a reboot: registers a
# Task Scheduler task that starts waitress on 127.0.0.1:8081 at boot, and
# serves the app when invoked with -Serve.
#
# MECHANISM: Task Scheduler, not a Windows service wrapper.
#   A service wrapper (NSSM, WinSW) would be new third-party software on a
#   production host, and this deployment's standing claim is that it added no
#   new software -- see SERVER_DEPLOYMENT.md. Task Scheduler is already the
#   mechanism for the daily task, so there is one thing to understand rather
#   than two, it survives a reboot, it restarts a crashed process, and it is
#   trivially portable to the replacement VPS. The honest cost: Task Scheduler
#   is not a service manager. It has no 'sc query' style status and it will not
#   notice a process that is alive but wedged -- which is why -Verify probes
#   /healthz over HTTP rather than trusting the task state.
#
# IDENTITY: NT AUTHORITY\SYSTEM, matching the daily task.
#   Least privilege would prefer LOCAL SERVICE, and that was considered and
#   rejected for now with a concrete reason: LOCAL SERVICE has no grant of any
#   kind on the project tree, the tracker database is owned by Administrators
#   with only ReadAndExecute for Users (and the app's create_all() issues DDL,
#   so it needs WRITE), and the password file is ACL'd SYSTEM:R +
#   Administrators:F. Running as LOCAL SERVICE therefore needs three ACL
#   changes on a live box, one of them to a secrets file, for an app that binds
#   loopback only and sits behind IIS. SYSTEM needs none. The least-privilege
#   version is recorded as an improvement in docs/INTERNAL_SITE.md rather than
#   pretended away.
#
# THE GUARD, and why it exists:
#   -Register and -Serve REFUSE unless the site password file exists. The site
#   runs UNAUTHENTICATED without it, and the ordering is enforced by this tool
#   rather than by anyone remembering. Loopback-only binding means an
#   unauthenticated instance is not reachable from outside today -- but the IIS
#   reverse-proxy site is a single command away, and defence that depends on
#   two facts staying true is weaker than defence that depends on one.
#
# USAGE
#   powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Register
#   powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Verify
#   powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Unregister
#   powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -TestRun -AllowUnauthenticated
#
# Pure ASCII by design.

[CmdletBinding()]
param(
    [switch]$Register,
    [switch]$Unregister,
    [switch]$Verify,
    [switch]$Serve,
    [switch]$TestRun,
    [switch]$Force,
    [switch]$AllowUnauthenticated,
    [string]$TaskName     = "MEPS EU Quota Site",
    [string]$ProjectRoot  = "C:\DataScienceProject\EUQuota",
    [string]$BindAddress  = "127.0.0.1",
    [int]   $Port         = 8081,
    [string]$PasswordFile = "C:\DataScienceProject\_secrets\quota-site-password.txt",
    [int]   $TestSeconds  = 8,
    [int]   $RetentionDays = 45
)

$ErrorActionPreference = "Stop"
$script:fail = 0

function Say  { param([string]$m) Write-Output $m }
function Step { param([string]$m) Write-Output ""; Write-Output ("=== " + $m + " ===") }
function Ok   { param([string]$m) Write-Output ("  PASS  " + $m) }
function Bad  { param([string]$m) Write-Output ("  FAIL  " + $m); $script:fail++ }
function Note { param([string]$m) Write-Output ("  NOTE  " + $m) }
function Die  { param([string]$m) Write-Output ""; Write-Output ("ABORT: " + $m); exit 1 }

$venvPython  = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$waitressExe = Join-Path $ProjectRoot "venv\Scripts\waitress-serve.exe"
$logDir      = Join-Path $ProjectRoot "data\logs"
$selfPath    = Join-Path $ProjectRoot "tools\quota-site-task.ps1"

function Assert-Environment {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Die "must run elevated"
    }
    if (-not (Test-Path $venvPython))  { Die "venv interpreter not found: $venvPython" }
    if (-not (Test-Path $waitressExe)) { Die "waitress-serve not found: $waitressExe -- pip install -r requirements-webapp.txt" }
    if (-not (Test-Path $logDir))      { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
}

# The guard. Deliberately blunt.
function Assert-PasswordFile {
    param([string]$What)
    if (Test-Path $PasswordFile) {
        Ok ("site password file present -- the site will require Basic auth")
        return
    }
    Say ""
    Say "  REFUSING to $What."
    Say ""
    Say "  The site password file does not exist:"
    Say ("    " + $PasswordFile)
    Say ""
    Say "  Without it webapp/app.py starts UNAUTHENTICATED. Set the password first:"
    Say "    powershell -ExecutionPolicy Bypass -File tools\set-site-password.ps1"
    Say ""
    Say "  This ordering is enforced here on purpose, so that it does not depend"
    Say "  on anyone remembering it. For a local smoke test only, and only on"
    Say "  loopback, use:  -TestRun -AllowUnauthenticated"
    Say ""
    exit 2
}

function Remove-OldLogs {
    if (-not (Test-Path $logDir)) { return }
    $cut = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem $logDir -Filter "site_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cut } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Get-Listening {
    return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-SiteProcesses {
    $stopped = 0
    Get-CimInstance Win32_Process -Filter "Name='waitress-serve.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -like "*webapp.app*" -or $_.ExecutablePath -eq $waitressExe) } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped++
        }
    return $stopped
}

# ---------------------------------------------------------------- serve ----
function Invoke-Serve {
    Assert-PasswordFile "serve"
    Remove-OldLogs
    $stamp = Get-Date -Format "yyyyMMdd"
    $log = Join-Path $logDir ("site_" + $stamp + ".log")
    $line = "{0} [INFO] starting waitress on {1}:{2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ssZ"), $BindAddress, $Port
    Add-Content -Path $log -Value $line -Encoding UTF8
    Set-Location $ProjectRoot
    & $waitressExe "--listen=$BindAddress`:$Port" "--call" "webapp.app:create_app" 2>&1 |
        ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
}

# ------------------------------------------------------------- register ----
function Invoke-Register {
    Step "Register the startup task"
    Assert-PasswordFile "register the task"

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        if (-not $Force) {
            Bad ("task '" + $TaskName + "' already exists. Re-run with -Force to replace it -- refusing to guess.")
            return
        }
        Note "removing the existing task (-Force)"
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $daily = Get-ScheduledTask -TaskName "MEPS EU Quota Daily Update" -ErrorAction SilentlyContinue
    if ($daily) { Ok "daily quota task found and untouched -- different task name, no collision" }

    $arg = ('-NonInteractive -NoProfile -ExecutionPolicy Bypass -File "{0}" -Serve -ProjectRoot "{1}" -BindAddress {2} -Port {3} -PasswordFile "{4}"' `
            -f $selfPath, $ProjectRoot, $BindAddress, $Port, $PasswordFile)
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    # ExecutionTimeLimit must be zero: this process is meant to run forever, and
    # the default three-day limit would silently kill the site.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    $desc = "Serves the internal quota tracker with waitress on $BindAddress`:$Port. Started at boot. See docs/INTERNAL_SITE.md."
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $desc | Out-Null

    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) { Bad "registration did not produce a task"; return }
    Ok ("registered '" + $TaskName + "'")
    Say ("        runs as    : " + $t.Principal.UserId + " (" + $t.Principal.LogonType + ", " + $t.Principal.RunLevel + ")")
    Say ("        trigger    : at startup")
    Say ("        time limit : " + $t.Settings.ExecutionTimeLimit + "  (PT0S = unlimited, required for a long-running process)")
    Say ("        on failure : restart " + $t.Settings.RestartCount + "x every " + $t.Settings.RestartInterval)
    Note "registered but NOT started. Start it with: Start-ScheduledTask -TaskName '$TaskName'"
}

# ----------------------------------------------------------- unregister ----
function Invoke-Unregister {
    Step "Unregister"
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        if ($t.State -eq "Running") { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Ok ("task '" + $TaskName + "' removed")
    } else {
        Note ("no task named '" + $TaskName + "' -- nothing to remove")
    }
    $n = Stop-SiteProcesses
    if ($n -gt 0) { Ok ("stopped " + $n + " serving process(es)") } else { Note "no serving process was running" }
    $l = Get-Listening
    if ($l.Count -eq 0) { Ok ("nothing listening on " + $Port) } else { Bad ("still listening on " + $Port) }
    Ok "the daily quota task is not touched by this script"
}

# --------------------------------------------------------------- verify ----
function Invoke-Verify {
    Step "Verify"
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        Ok ("task exists, state=" + $t.State + ", runs as " + $t.Principal.UserId)
        $i = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($i) { Say ("        last run " + $i.LastRunTime + "  result " + $i.LastTaskResult) }
    } else {
        Note ("task '" + $TaskName + "' is not registered")
    }

    if (Test-Path $PasswordFile) { Ok "site password file present" }
    else { Note "site password file ABSENT -- the site would run UNAUTHENTICATED, and -Register will refuse" }

    $l = Get-Listening
    if ($l.Count -gt 0) {
        Ok ("something is listening on " + $Port)
        foreach ($x in $l) { Say ("        " + $x.LocalAddress + ":" + $x.LocalPort) }
        # trust the port as little as the task state: prove it answers
        try {
            $r = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $Port + "/healthz") -UseBasicParsing -TimeoutSec 10
            Ok ("/healthz answered HTTP " + [int]$r.StatusCode)
        } catch {
            $code = 0
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -eq 401) { Ok "/healthz returned 401 -- serving, and authentication is on" }
            else { Bad ("listening but /healthz did not answer: " + $_.Exception.Message.Split([char]10)[0]) }
        }
    } else {
        Note ("nothing listening on " + $Port + " -- the site is not serving")
    }

    foreach ($b in @("0.0.0.0", "::")) {
        if ($l | Where-Object { $_.LocalAddress -eq $b }) {
            Bad ("BOUND TO " + $b + " -- this must be loopback only")
        }
    }
}

# -------------------------------------------------------------- testrun ----
function Invoke-TestRun {
    Step "Test run (foreground, temporary)"
    if (-not (Test-Path $PasswordFile) -and -not $AllowUnauthenticated) {
        Assert-PasswordFile "test-run"
    }
    if (-not (Test-Path $PasswordFile)) {
        Note "NO PASSWORD FILE: this test will serve UNAUTHENTICATED for a few seconds."
        Note "Permitted only because the bind address is loopback and it is torn down below."
    }
    if ($BindAddress -ne "127.0.0.1" -and $BindAddress -ne "::1") {
        Die "refusing to test-run on a non-loopback address ($BindAddress)"
    }

    $before = (Get-Listening).Count
    if ($before -gt 0) { Bad ("something is already listening on " + $Port + " -- refusing to start a second instance"); return }

    $job = Start-Job -ScriptBlock {
        param($exe, $root, $bind, $port)
        Set-Location $root
        & $exe "--listen=$bind`:$port" "--call" "webapp.app:create_app" 2>&1
    } -ArgumentList $waitressExe, $ProjectRoot, $BindAddress, $Port

    Start-Sleep -Seconds 6
    try {
        foreach ($p in @("/healthz", "/")) {
            try {
                $r = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $Port + $p) -UseBasicParsing -TimeoutSec 15
                Ok ("{0,-10} HTTP {1}, {2:N0} bytes" -f $p, [int]$r.StatusCode, $r.Content.Length)
            } catch {
                $code = 0
                if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
                if ($code -eq 401) { Ok ("{0,-10} HTTP 401 -- authentication required, as intended" -f $p) }
                else { Bad ("{0,-10} {1}" -f $p, $_.Exception.Message.Split([char]10)[0]) }
            }
        }
    } finally {
        Step "Tear down"
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        $n = Stop-SiteProcesses
        Start-Sleep -Seconds 2
        $after = Get-Listening
        if ($after.Count -eq 0) { Ok ("nothing left listening on " + $Port + " (stopped " + $n + " process(es))") }
        else { Bad ("STILL LISTENING on " + $Port + " after teardown -- investigate") }
    }
}

# ------------------------------------------------------------------ main ---
if ($Serve) { Assert-Environment; Invoke-Serve; exit 0 }

Say "Internal quota tracker -- startup task"
Say ("project : " + $ProjectRoot)
Say ("bind    : " + $BindAddress + ":" + $Port + "  (loopback only, by design)")
Say ("task    : " + $TaskName)
Assert-Environment

if (-not ($Register -or $Unregister -or $Verify -or $TestRun)) {
    Say ""
    Say "Nothing to do. Pass -Register, -Unregister, -Verify or -TestRun."
    exit 0
}

if ($TestRun)    { Invoke-TestRun }
if ($Register)   { Invoke-Register }
if ($Unregister) { Invoke-Unregister }
if ($Verify)     { Invoke-Verify }

Say ""
if ($script:fail -eq 0) { Say "OK - no failures."; exit 0 }
Say ("FAILURES: " + $script:fail)
exit $script:fail
