# assert-inert.ps1
#
# Proves that the server copy of this project cannot publish anything.
#
# "It is not live yet" is a belief. This is an assertion that fails loudly.
# Run it after deploying, after any change to the deployment, and any time you
# are about to do something on the server while GitHub Actions is still the
# live pipeline -- two hosts publishing the same day race on git push.
#
# Exit code 0 = inert. Non-zero = the number of guards that failed.
#
# After cutover this script is EXPECTED to fail on the task and token checks:
# that is what cutover means. Use -PostCutover to assert the opposite, i.e.
# that the deployment is correctly live.
#
# Pure ASCII by design.

param(
    [string]$ProjectRoot = "C:\DataScienceProject\EUQuota",
    [string]$TokenFile   = "C:\DataScienceProject\_secrets\euquota-github.token",
    [string]$TaskName    = "MEPS EU Quota Daily Update",
    [switch]$PostCutover
)

$ErrorActionPreference = "Continue"
$fail = 0

function Check {
    param([string]$Label, [bool]$Ok, [string]$Detail = "")
    if ($Ok) { "PASS  $Label $Detail" }
    else     { "FAIL  $Label $Detail"; $script:fail++ }
}

$mode = if ($PostCutover) { "LIVE (post-cutover)" } else { "INERT (pre-cutover)" }
"Asserting the deployment is: $mode"
""

# --- the scheduled task ---------------------------------------------------
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($PostCutover) {
    Check "scheduled task exists" ($null -ne $task)
    if ($task) {
        $trigger = ($task.Triggers | ForEach-Object { $_.StartBoundary }) -join ", "
        $principal = $task.Principal.UserId
        Check "task runs as SYSTEM" ($principal -match "SYSTEM") "(is: $principal)"
        Check "task is enabled" ($task.State -ne "Disabled") "(state: $($task.State))"
        "      trigger: $trigger"
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($info) {
            # 267011 = 0x41303 = SCHED_S_TASK_HAS_NOT_RUN, paired with a 1899/1932
            # sentinel date. It appears after a re-registration, which resets run
            # history, and reads exactly like a failure if you do not know it.
            $res = switch ($info.LastTaskResult) {
                0      { "0 (success)" }
                267011 { "not yet run since registration (0x41303) - not a failure" }
                267009 { "currently running (0x41301)" }
                267014 { "last run was terminated by the user (0x41306)" }
                default { "$($info.LastTaskResult) - see the run log" }
            }
            $when = if ($info.LastTaskResult -eq 267011) { "never" } else { $info.LastRunTime }
            "      last run: $when   result: $res"
            "      next run: $($info.NextRunTime)"
            "      on failure: restart $($task.Settings.RestartCount)x every $($task.Settings.RestartInterval)"
        }
    }
} else {
    $any = Get-ScheduledTask | Where-Object {
        $_.TaskName -eq $TaskName -or
        ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -match "EUQuota"
    }
    Check "no scheduled task references this project" ($null -eq $any)
}

# --- the credential -------------------------------------------------------
$tokenExists = Test-Path $TokenFile
if ($PostCutover) {
    Check "push token is present" $tokenExists
    if ($tokenExists) {
        $bytes = [System.IO.File]::ReadAllBytes($TokenFile)
        $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
        Check "token has no BOM" (-not $bom)
        Check "token has no trailing newline" ($bytes[$bytes.Length-1] -ne 10 -and $bytes[$bytes.Length-1] -ne 13)
        $acl = (& icacls.exe $TokenFile) -join " "
        Check "token not readable by Users" ($acl -notmatch "BUILTIN\\Users|Everyone")
    }
} else {
    Check "no push token exists (so -Push cannot succeed)" (-not $tokenExists)
}

# --- the repository -------------------------------------------------------
# Read the STORED url, not the effective one. `git remote get-url` applies
# url.<base>.insteadOf rewriting from the *calling account's* global config,
# and the Administrator profile on this host rewrites https://github.com/ to
# git@github.com:. The scheduled task runs as SYSTEM, which has no such rule
# and no SSH key, so what matters is the raw value in .git/config -- that is
# the url SYSTEM will use with GIT_ASKPASS and the token.
#
# Checking the effective url here made this guard FAIL for an Administrator
# running it by hand while the task's own path was perfectly fine. A guard that
# cries wolf gets ignored, which is worse than no guard.
$origin = & git -C $ProjectRoot config --get remote.origin.url
Check "origin points at GitHub over https" ($origin -eq "https://github.com/salt0401/EU-Quota.git") "(stored: $origin)"

# Not a failure -- but if a rewrite is active for whoever is running this, say
# so, because it means THIS account pushes over a different transport with a
# different credential than the task does. A manual push succeeding proves
# nothing about the task in that case.
$rewrite = & git -C $ProjectRoot config --get-regexp "^url\..*\.insteadof$" 2>$null
if ($rewrite) {
    "NOTE  a url.insteadOf rewrite is active for this account:"
    $rewrite | ForEach-Object { "        $_" }
    $effective = & git -C $ProjectRoot remote get-url origin
    "        origin resolves to: $effective"
    "        SYSTEM has no such rule, so the task still uses the stored https url."
}

$dirty = & git -C $ProjectRoot status --porcelain
Check "working tree is clean" ([string]::IsNullOrWhiteSpace($dirty -join "")) "($(($dirty | Measure-Object).Count) changed)"

# --- the script's own guard ----------------------------------------------
# Publication is gated on -Push inside the task script. Assert the switch is
# still declared and still gates the upload/push section.
$taskScript = Join-Path $ProjectRoot "tools\server-daily-task.ps1"
$src = Get-Content $taskScript -Raw
$hasSwitch = $src.Contains('[switch]$Push')
$hasGate   = $src.Contains('if (-not $Push)')
Check "task script declares the -Push switch" $hasSwitch
Check "task script returns early without -Push" $hasGate

# --- the UTC date guard ---------------------------------------------------
$guarded = $src.Contains('Local date ($localDate) and UTC date ($utcDate) disagree')
Check "task script carries the UTC/local date guard" $guarded

""
if ($fail -eq 0) {
    if ($PostCutover) { "ALL GUARDS ASSERTED - the deployment is correctly LIVE." }
    else              { "ALL GUARDS ASSERTED - the server copy is INERT and cannot publish." }
} else {
    "$fail GUARD(S) FAILED - do not proceed until this is understood."
}
exit $fail
