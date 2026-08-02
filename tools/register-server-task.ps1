# register-server-task.ps1
#
# Registers (or re-registers) the daily scheduled task on the MEPS company
# server. Kept in the repo rather than run ad hoc so the deployment is
# reproducible -- see docs/SERVER_DEPLOYMENT.md.
#
#   powershell -ExecutionPolicy Bypass -File tools\register-server-task.ps1
#   powershell -ExecutionPolicy Bypass -File tools\register-server-task.ps1 -Force
#
# -Force replaces an existing task. Without it the script refuses, so a
# re-run cannot silently change a working schedule.
#
# Pure ASCII by design.

param(
    [string]$TaskName    = "MEPS EU Quota Daily Update",
    [string]$ProjectRoot = "C:\DataScienceProject\EUQuota",
    [string]$At          = "06:40",
    [int]   $RetryCount  = 2,
    [int]   $RetryMins   = 20,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if (-not $Force) {
        throw "Task '$TaskName' already exists. Re-run with -Force to replace it."
    }
    "Removing the existing task (-Force)..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$script = Join-Path $ProjectRoot "tools\server-daily-task.ps1"
if (-not (Test-Path $script)) { throw "Task script not found at $script" }

# -ExecutionPolicy Bypass: LocalMachine policy is RemoteSigned, and a .ps1 that
# arrived from elsewhere can carry a mark-of-the-web that blocks it.
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -NoProfile -ExecutionPolicy Bypass -File `"$script`" -Push" `
    -WorkingDirectory $ProjectRoot

# 06:40 LOCAL. Clear of MEPS Currency API (06:00) and MEPS SteelNews Scrape
# (07:15), and >= 05:30 UTC in both seasons (05:40 UTC in summer, 06:40 in
# winter) so it always lands after the UK Trade Tariff refresh and the TARIC
# morning allocation.
$trigger = New-ScheduledTaskTrigger -Daily -At $At

# SYSTEM with ServiceAccount logon: no stored password, and it fires whether or
# not anyone is signed in. Running as the shared Administrator would need that
# password stored in the task, or would only fire during an interactive session.
$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# RestartCount/RestartInterval: retry a FAILED run rather than losing the day.
#
# Safe to do because the publish is idempotent -- update_history_csv() replaces
# rows per (date, region) rather than appending, and the release upload deletes
# an asset of the same name before re-uploading -- so a retry that follows a
# partial run converges on the same result rather than doubling anything.
#
# The GitHub Actions job this replaced had no retry, but the situations differ:
# a hosted runner had a fresh environment and good connectivity, whereas here a
# single transient network blip costs a whole day of history. Two attempts
# twenty minutes apart still finish long before the 07:15 steel-news job.
#
# MultipleInstances IgnoreNew prevents a retry from overlapping a run that is
# somehow still going.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew `
    -RestartCount $RetryCount `
    -RestartInterval (New-TimeSpan -Minutes $RetryMins)

$desc = "Scrapes EU TARIC (283) and UK Trade Tariff (75) steel tariff quotas, " +
        "builds the MEPS customer report, and publishes to GitHub. Replaced the " +
        "GitHub Actions job on 2026-08-02. Runbook: docs\SERVER_DEPLOYMENT.md in " +
        "the project folder. Touches no database, no IIS site and no other task."

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description $desc | Out-Null

""
"=== Registered ==="
$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"  Name        : $($t.TaskName)"
"  State       : $($t.State)"
"  Runs as     : $($t.Principal.UserId) ($($t.Principal.LogonType), $($t.Principal.RunLevel))"
"  Trigger     : $($t.Triggers.StartBoundary)"
"  Next run    : $($i.NextRunTime)"
"  Action      : $($t.Actions.Execute) $($t.Actions.Arguments)"
"  Time limit  : $($t.Settings.ExecutionTimeLimit)"
"  On failure  : restart $($t.Settings.RestartCount)x every $($t.Settings.RestartInterval)"
"  Overlap     : $($t.Settings.MultipleInstances)"
""
"Local now   : $((Get-Date).ToString('yyyy-MM-dd HH:mm'))"
"UTC now     : $([datetime]::UtcNow.ToString('yyyy-MM-dd HH:mm'))"
