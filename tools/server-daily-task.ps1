# server-daily-task.ps1
#
# Daily EU + UK quota scrape and publish, for Windows Task Scheduler on the
# MEPS company server. Replaces the GitHub Actions job that ran this until
# cutover. See docs/SERVER_DEPLOYMENT.md.
#
# PURE ASCII BY DESIGN. Windows PowerShell 5.1 reads a BOM-less file as ANSI,
# so a single non-ASCII character breaks string parsing with errors that point
# at unrelated lines. Parse-check before first use.
#
# SAFETY: publishing is opt-in. Without -Push this scrapes, builds the report
# and updates data/published/ locally, but pushes nothing and uploads nothing.
# That is what makes a bring-up run safe while GitHub Actions is still live --
# two hosts publishing the same day would race on git push.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File server-daily-task.ps1
#   powershell -ExecutionPolicy Bypass -File server-daily-task.ps1 -Push

param(
    [switch]$Push,
    [switch]$SkipScrape,
    [string]$ProjectRoot      = "C:\DataScienceProject\EUQuota",
    [string]$TokenFile        = "C:\DataScienceProject\_secrets\euquota-github.token",
    [string]$Branch           = "main",
    [int]   $LogRetentionDays = 45
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------- logging ---

$logDir = Join-Path $ProjectRoot "data\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("server_{0}.log" -f (Get-Date).ToUniversalTime().ToString("yyyyMMdd"))

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
    $line = "{0}Z [{1}] {2}" -f $stamp, $Level, $Message
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Fail {
    param([string]$Message)
    Write-Log $Message "ERROR"
    Write-Log "=== RUN FAILED ===" "ERROR"
    exit 1
}

# Judge native commands by exit code, never by stderr. Git, pip and curl all
# write ordinary progress to stderr, and PowerShell 5.1 with
# ErrorActionPreference=Stop treats that as fatal even on exit code 0.
function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments, [string]$What, [switch]$AllowFailure)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $Exe @Arguments 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    foreach ($line in $output) { Write-Log ("    " + $line) }
    if ($code -ne 0 -and -not $AllowFailure) {
        Fail ("{0} failed with exit code {1}" -f $What, $code)
    }
    return $code
}

Write-Log "=== EU Quota daily update starting ==="
Write-Log ("Push mode: {0}" -f $(if ($Push) { "LIVE (will commit, push and upload)" } else { "INERT (local only)" }))

# ------------------------------------------------------------- preflight ---

$venvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Fail "venv interpreter not found at $venvPython. Bare 'python' on this box is 3.13, not this project's 3.12 -- always use the full path."
}
if (-not (Test-Path (Join-Path $ProjectRoot ".git"))) {
    Fail "$ProjectRoot is not a git working copy."
}
if ($Push -and -not (Test-Path $TokenFile)) {
    Fail "-Push was requested but the token file $TokenFile does not exist."
}

# The timezone trap. This server runs GMT Standard Time -- UTC in winter, UTC+1
# in summer -- and Task Scheduler fires on LOCAL time. publish_data() stamps
# rows with date.today(), which is local. At the 06:40 slot the two dates always
# agree, but if the trigger is ever moved into 00:00-01:00 local they would not,
# and a whole day of history would be filed under the wrong date. Fail loudly
# rather than publish silently-wrong data.
$utcDate   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
$localDate = (Get-Date).ToString("yyyy-MM-dd")
Write-Log ("Date check -- local {0} / UTC {1}" -f $localDate, $utcDate)
if ($utcDate -ne $localDate) {
    Fail "Local date ($localDate) and UTC date ($utcDate) disagree. The scheduled trigger has drifted into the pre-01:00 window where local time and UTC fall on different days. Move the trigger later; do not publish under an ambiguous date."
}

Set-Location $ProjectRoot

# UTF-8 is not optional here: the pipeline handles 'Turkiye' and en-dashes in
# regulation text, and a non-UTF-8 console codepage crashes the run.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# ---------------------------------------------------------------- scrape ---

if ($SkipScrape) {
    Write-Log "SkipScrape set -- reusing whatever is already in data/published/." "WARN"
} else {
    Write-Log "Scraping EU + UK quotas and publishing locally..."
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-Native $venvPython @("run.py", "--publish") "run.py --publish" | Out-Null
    $sw.Stop()
    Write-Log ("Scrape and local publish completed in {0:N0}s" -f $sw.Elapsed.TotalSeconds)
}

# Report what the run actually produced, so a failure leaves evidence in the log.
$metaPath = Join-Path $ProjectRoot "data\published\metadata.json"
if (Test-Path $metaPath) {
    $meta = Get-Content $metaPath -Raw | ConvertFrom-Json
    Write-Log ("metadata: data_date={0} eu={1} (failed {2}) uk={3} (failed {4}) history_rows={5}" -f `
        $meta.data_date, $meta.eu_quotas, $meta.eu_failed, $meta.uk_quotas, $meta.uk_failed, $meta.history_rows)
    if ($meta.data_date -ne $utcDate) {
        Fail ("metadata.json reports data_date {0} but this run is for {1}. Refusing to publish a mislabelled day." -f $meta.data_date, $utcDate)
    }
} else {
    Fail "data/published/metadata.json was not produced -- the publish step did not complete."
}

if (-not $Push) {
    Write-Log "INERT run complete. Nothing was pushed or uploaded."
    Write-Log "Discard the local publish with: git checkout -- data/published/"
    Write-Log "=== RUN OK (inert) ==="
    exit 0
}

# ------------------------------------------------------- publish upstream ---

# Assets go up BEFORE metadata is pushed. An asset that metadata does not yet
# name is inert; pushed metadata naming a not-yet-uploaded asset 404s in every
# colleague's downloader. This bites on the first run of each calendar year,
# when the new year's workbook name does not exist on the release yet.
Write-Log "Uploading workbooks to the 'latest-data' release..."
Invoke-Native $venvPython @("tools\publish_release_assets.py", "--token-file", $TokenFile) "release asset upload" | Out-Null

Write-Log "Committing and pushing published data (csv + metadata only)..."

# Identity is set per-repository so nothing global on this shared box changes.
Invoke-Native "git" @("config", "user.name", "meps-server-euquota") "git config user.name" | Out-Null
Invoke-Native "git" @("config", "user.email", "euquota@meps.local") "git config user.email" | Out-Null

# Credentials reach git through GIT_ASKPASS reading the token file, so the
# token never appears on a command line (visible in the process list on a
# shared machine) and never lands in .git/config. GIT_TERMINAL_PROMPT=0 makes a
# credential problem fail immediately instead of hanging an unattended task.
$env:EUQUOTA_TOKEN_FILE = $TokenFile
$env:GIT_ASKPASS = Join-Path $ProjectRoot "tools\git-askpass.cmd"
$env:GIT_TERMINAL_PROMPT = "0"

# Git Credential Manager is the default helper on Git for Windows and opens a
# GUI prompt when it has no cached credential. Under a scheduled task running
# as SYSTEM there is no desktop to show it on, so the task would hang forever
# instead of failing. Passing "-c credential.helper=" resets the helper list
# for that one invocation.
#
# It is written as a single "-c credential.helper=" pair rather than
# `git config credential.helper ""` because PowerShell drops an empty-string
# element when splatting an array to a native command -- which silently turns
# the write into a read and leaves the manager active.
$GitNoHelper = @("-c", "credential.helper=")

Invoke-Native "git" @("add", "data/published/quota_history_2026.csv", "data/published/metadata.json") "git add" -AllowFailure | Out-Null
# Re-add by glob for any additional year files that exist (new calendar years).
Invoke-Native "git" @("add", "--", "data/published/") "git add published dir" | Out-Null

$staged = Invoke-Native "git" @("diff", "--cached", "--quiet") "git diff --cached" -AllowFailure
if ($staged -eq 0) {
    Write-Log "No data changes to publish (identical to the last commit)."
} else {
    Invoke-Native "git" @("commit", "-m", "data: daily quota update $utcDate") "git commit" | Out-Null

    # Tolerate a manual push that landed while we were scraping, exactly as the
    # Actions job did.
    $rebased = Invoke-Native "git" ($GitNoHelper + @("pull", "--rebase", "origin", $Branch)) "git pull --rebase" -AllowFailure
    if ($rebased -ne 0) {
        Write-Log "Rebase hit a conflict -- aborting and retrying with -X theirs." "WARN"
        Invoke-Native "git" @("rebase", "--abort") "git rebase --abort" -AllowFailure | Out-Null
        Invoke-Native "git" ($GitNoHelper + @("pull", "--rebase", "-X", "theirs", "origin", $Branch)) "git pull --rebase -X theirs" | Out-Null
    }

    Invoke-Native "git" ($GitNoHelper + @("push", "origin", $Branch)) "git push" | Out-Null
    Write-Log "Pushed data: daily quota update $utcDate"
}

Remove-Item Env:\EUQUOTA_TOKEN_FILE, Env:\GIT_ASKPASS -ErrorAction SilentlyContinue

# ------------------------------------------------------------- retention ---

$cutoff = (Get-Date).AddDays(-$LogRetentionDays)
Get-ChildItem -Path $logDir -Filter "server_*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Write-Log ("Pruning old log {0}" -f $_.Name)
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }

Write-Log "=== RUN OK (live) ==="
exit 0
