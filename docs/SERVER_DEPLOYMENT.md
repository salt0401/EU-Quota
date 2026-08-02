# Server deployment — the daily run on the MEPS company server

Since August 2026 the daily EU + UK quota scrape runs on the **MEPS company
server**, not on GitHub Actions. This document is the operational reference for
that: what is installed where, how a run works, and what to do when one fails.

> **Status — 2026-08-02: LIVE.** Cut over and verified. The GitHub Actions
> schedule is disabled, the scheduled task is registered and enabled, and the
> first live run published `data_date=2026-08-02` (283 EU / 0 failed,
> 75 UK / 0 failed, 10,024 history rows) — commit `b20a798` on `main`, authored
> by `meps-server-euquota`, with both release workbooks updated.

For anything about the server *itself* — access, firewalls, other workloads,
constraints — read the separate **`meps-server-docs`** repository. This file
covers only what is specific to this project.

---

## At a glance

| | |
|---|---|
| **Host** | `WIN-RE1UH50A07U` · `212.227.127.169` · Windows Server 2019 |
| **Location** | `C:\DataScienceProject\EUQuota` — sibling of `MEPSWebsScrap`, per the server's layout convention |
| **Interpreter** | `C:\DataScienceProject\EUQuota\venv\Scripts\python.exe` (Python **3.12.10**) |
| **Scheduled task** | `MEPS EU Quota Daily Update`, daily **06:40 local**, runs as `SYSTEM` |
| **Entry point** | `tools\server-daily-task.ps1 -Push` |
| **Run log** | `C:\DataScienceProject\EUQuota\data\logs\server_<YYYYMMDD>.log` (45-day retention) |
| **Credential** | `C:\DataScienceProject\_secrets\euquota-github.token` — outside every repo |
| **Publishes to** | The same GitHub repo and `latest-data` release as before. **Colleagues' downloader is unchanged.** |
| **Watched by** | `.github/workflows/data-freshness-watchdog.yml`, running on GitHub |

> ⚠️ **`python` on this server is NOT this project's Python.** Three interpreters
> coexist and bare `python` / `py` both resolve to **3.13.1**. Always use the
> full venv path above. A script relying on bare `python` runs under the wrong
> interpreter, silently.

---

## Why the daily run moved

The company server is a **standing requirement** for MEPS data projects, not a
cost optimisation. Worth stating plainly because the obvious assumption is
wrong: `salt0401/EU-Quota` is a **public** repository, and public repositories
get unlimited free GitHub Actions minutes. Nothing was being consumed. The move
is about where MEPS work is hosted, and it puts this project alongside the steel
news pipeline under one parent folder.

What did **not** change: the pipeline, the data format, the publish targets, the
release assets, and every installed `MEPS_Quota_Downloader.exe`. Only the
machine that runs the scrape is different.

---

## What a run does

```
06:40 local  Task Scheduler
  |
  +-- tools\server-daily-task.ps1 -Push
       |
       1. Preflight: venv exists, git working copy, token file present
       2. Date guard: local date == UTC date, or refuse to publish
       3. venv\Scripts\python.exe run.py --publish
       |     -> data/output/<date>/ (report + raw workbooks, gitignored)
       |     -> data/published/quota_history_<YEAR>.csv   (appended, idempotent)
       |     -> data/published/metadata.json
       |     -> data/published/*.xlsx                      (gitignored)
       4. Assert metadata.json names today
       5. tools\publish_release_assets.py -> uploads workbooks to 'latest-data'
       6. git commit + pull --rebase + push  (csv + metadata only)
```

**Step 5 runs before step 6, deliberately.** An asset that `metadata.json` does
not yet name is inert; pushed metadata naming a not-yet-uploaded asset **404s in
every colleague's downloader**. This bites on the first run of each calendar
year, when the new year's workbook name does not exist on the release yet. The
GitHub Actions job had the same ordering, for the same reason.

A run takes **~200 seconds**. Expect `283 EU / 75 UK`, both with `0 failed`.

---

## The three guards, and why each exists

**1. Publishing is opt-in (`-Push`).** Without the flag the script scrapes and
writes `data/published/` locally but pushes nothing and uploads nothing. This is
what makes a bring-up or debugging run safe. Discard its output with:

```
git checkout -- data/published/
```

**2. The date guard.** Task Scheduler fires on *local* time, and this server
runs `GMT Standard Time` — UTC in winter, **UTC+1 in summer**. `publish_data()`
stamps rows with `date.today()`, which is local, whereas the GitHub runner this
replaced was always UTC. Between 00:00 and 01:00 local in summer the two dates
disagree, and publishing then would file a whole day of history *a day ahead* of
every previous row. A `-Push` run in that window fails loudly; an inert run
warns and continues.

This is not theoretical on this host: `MEPS Currency API` has a 06:00 trigger and
has been observed running at 07:00.

> **If you trigger a run by hand, gate on the server's clock, not your own.**
> During cutover a manual run was fired "just after midnight UTC" according to a
> laptop that turned out to be **6 minutes fast** — the server, verified accurate
> to 3 seconds against three independent public `Date` headers, was still on the
> previous UTC day, and the guard correctly refused. Check first:
>
> ```powershell
> [datetime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss")
> ```
>
> (`Get-Date -UFormat %s` is not a UTC epoch in PowerShell 5.1 — it derives from
> local time and reads an hour high under BST.)

**3. The pipeline's own publish gates** (`src/publisher.py`, unchanged) refuse to
publish a mostly-failed scrape or an expired quota window. Those failures are
covered by `DAILY_UPDATE_RUNBOOK.md`, not this file.

### Retry on failure

The task retries **twice, twenty minutes apart**, if a run fails.

This is safe *because the publish is idempotent*, not merely because retrying is
usually harmless: `update_history_csv()` replaces rows per `(date, region)`
rather than appending, and the release upload deletes an asset of the same name
before re-uploading. A retry after a partial run therefore converges on the same
result instead of doubling anything.

The GitHub Actions job this replaced had no retry, and the difference is
deliberate: a hosted runner had a fresh environment and good connectivity,
whereas here a single transient network blip would otherwise cost a whole day of
history. Two attempts twenty minutes apart still finish well before the 07:15
steel-news job. `MultipleInstances IgnoreNew` prevents a retry overlapping a run
that is somehow still going.

A retry does **not** rescue a genuine failure — a stale quarter, a regulation
renewal, an expired token — it just tries again and fails again, which the
watchdog reports as normal.

---

## The credential

A **fine-grained** GitHub PAT, scoped to `salt0401/EU-Quota` only, with
`Contents: Read and write`. Nothing else.

It is stored at `C:\DataScienceProject\_secrets\euquota-github.token`,
**outside every git working copy**, readable only by `SYSTEM` and
`Administrators`. It reaches git through `GIT_ASKPASS` at run time, so it never
appears on a command line (visible in the process list on a shared machine) and
never lands in `.git/config`.

Set or rotate it with:

```
ssh -i ~/.ssh/meps_vps_ed25519 Administrator@212.227.127.169
powershell -ExecutionPolicy Bypass -File C:\DataScienceProject\EUQuota\tools\set-github-token.ps1
```

**Why fine-grained and single-repo matters here.** This host is internet-facing,
is over a year behind on patches, has SQL Server exposed on 1433, and is backed
up by Acronis to storage MEPS does not control. A credential placed here should
be assumed to be *reachable*. Scoped as above, the worst case is someone writing
to one repository whose entire contents are already public — which is about as
contained as a write credential gets.

**The run warns you before it expires.** GitHub returns the token's expiry on
every authenticated response, so `publish_release_assets.py` reads it from a call
it already makes and logs one of:

```
  Token expiry: 2027-08-02 (365 days away)
  WARNING: the push token expires on 2026-08-16, in 12 day(s). Re-issue it ...
  WARNING: the push token EXPIRED on 2026-08-01. Re-issue it ...
```

The warning starts **14 days out**, so expiry is two weeks' notice rather than a
surprise outage. The check never fails the run: a token that still works today
must publish today's data even if the lookup cannot answer.

> **As deployed on 2026-08-02 the token has NO expiry** — the check reports
> `Token expiry: none set (the token does not expire)`.
>
> That is a deliberate trade, and worth restating so it can be revisited. A
> non-expiring token never breaks the pipeline; an expiring one breaks it if a
> renewal is missed. Against that: a write credential that never rotates sits
> indefinitely on an internet-facing host that is over a year behind on patches
> and is backed up to storage MEPS does not control.
>
> **Recommendation: set a 1-year expiry.** The main argument against rotation —
> that it fails silently and inconveniently — is now largely answered by the
> warning above plus the freshness watchdog. Re-issue with
> `tools/set-github-token.ps1`; nothing else needs to change.

### Two encoding traps

The token file must be **UTF-8 with no BOM** and have **no trailing newline**.
`git-askpass.cmd` emits it with `type`, so a BOM would be prepended to the
credential and GitHub would reject it. Windows PowerShell 5.1 writes a BOM by
default from both `Set-Content` and `Out-File` — `set-github-token.ps1` uses
.NET directly to avoid this, and verifies the result.

### Git Credential Manager must not be reached

GCM is the default credential helper on Git for Windows and opens a **GUI
prompt** when it has no cached credential. A scheduled task running as `SYSTEM`
has no desktop to show it on, so the push would **hang indefinitely** rather than
fail — and a hung unattended job is strictly worse than a failed one.

The task script therefore passes `-c credential.helper=` on every git
invocation. Note that this cannot be done with `git config credential.helper ""`
from PowerShell: an empty-string element is dropped when an array is splatted to
a native command, which silently turns the write into a *read* and leaves the
manager active. That was caught during deployment.

---

## Monitoring

Nothing on this server notices a scheduled task that never fires. Windows Task
Scheduler has no alerting, and a job that does not start cannot report that it
did not start.

`.github/workflows/data-freshness-watchdog.yml` is the external heartbeat. It
runs on **GitHub**, not here — a watchdog hosted on the machine it watches is not
a watchdog — at 09:00 UTC daily, and asserts one fact: does the committed
`metadata.json` name today's date? That single assertion covers every failure
mode, because the task not firing, the scrape failing, the gates refusing and the
push failing all end the same way: metadata does not advance.

It opens an issue titled **"Daily quota update has not published today"**, comments
on it while the problem persists, and closes it automatically on recovery.

---

## Triage

```bash
ssh -i ~/.ssh/meps_vps_ed25519 Administrator@212.227.127.169 "Get-ScheduledTaskInfo -TaskName 'MEPS EU Quota Daily Update'"
```

`LastTaskResult` of `0` means the script ran and succeeded. Then read the log:

```bash
ssh -i ~/.ssh/meps_vps_ed25519 Administrator@212.227.127.169 "Get-Content C:\DataScienceProject\EUQuota\data\logs\server_$(date -u +%Y%m%d).log"
```

| Symptom in the log | Cause | Fix |
|---|---|---|
| `venv interpreter not found` | The venv was deleted or the folder moved | Rebuild: `C:\Python312\python.exe -m venv venv` then `pip install -r requirements-ci.txt` |
| `-Push was requested but the token file ... does not exist` | Credential missing or rotated away | Re-run `set-github-token.ps1` |
| `Local date ... and UTC date ... disagree` | The trigger drifted into the pre-01:00 window — **or you triggered it manually from a workstation whose clock is ahead of the server's** | Move the trigger back to 06:40 local. For a manual run, check the server's own clock first (see below) |
| `metadata.json reports data_date ...` mismatch | The publish reused stale metadata | Investigate before re-running; do not force |
| `release asset upload failed` | Token expired, or GitHub unavailable | Check the token first — expiry is the usual cause |
| `git push failed` (401) | Token expired or lost `Contents: write` | Re-issue the token |
| Task never ran at all | Task disabled, or the box rebooted mid-window | Check `Get-ScheduledTask`; re-enable |
| Intermittent `WinError 32` on a rename | Antivirus holding a handle — see below | Re-run; if it recurs, request exclusions |

### The antivirus failure signature

Windows Defender real-time scanning **and** Acronis Active Protection both watch
file writes on this host, with **no exclusions** (a standing owner decision —
SQL Server runs here without exclusions too). The predicted symptom is an
**intermittent** `PermissionError` / `WinError 32` on `os.replace`, `os.rename`
or `shutil.move`, on a file this code just wrote, which **succeeds on an
immediate re-run**.

If you see that, do not start by suspecting the Python. Request a path exclusion
for `C:\DataScienceProject` in both products, then re-test.

*(`src/publisher.py` already tolerates the most likely instance of this: a
workbook locked by Excel is skipped with a warning rather than crashing the
publish, and the canonical csv/metadata are written first for that reason.)*

---

## Emergency fallback

`.github/workflows/daily-quota-update.yml` still exists, with its `schedule:`
block commented out and `workflow_dispatch` intact. If the server is down:

> GitHub → Actions → **Daily quota update** → **Run workflow**

That publishes from a GitHub runner exactly as before.

⚠️ **Only do this once the server task is confirmed not running.** Two hosts
publishing the same day race on `git push` — the history append itself is
idempotent per `(date, region)`, so the data would not corrupt, but one of the
two runs fails noisily and the release assets may end up from the losing run.

---

## Re-deploying from scratch

```powershell
# on a machine with the repo
git bundle create EUQuota.bundle HEAD main
# note the sha256, copy it over, verify on the server, then:
git clone EUQuota.bundle C:\DataScienceProject\EUQuota
cd C:\DataScienceProject\EUQuota
git remote set-url origin https://github.com/salt0401/EU-Quota.git
git config credential.https://github.com.username x-access-token
git config user.name  meps-server-euquota
git config user.email euquota@meps.local
C:\Python312\python.exe -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-ci.txt pytest
venv\Scripts\python.exe -m pytest tests -q          # expect 222 passed

# credential, then the scheduled task
powershell -ExecutionPolicy Bypass -File tools\set-github-token.ps1
powershell -ExecutionPolicy Bypass -File tools\register-server-task.ps1

# prove it before trusting it
powershell -ExecutionPolicy Bypass -File tools\assert-inert.ps1 -PostCutover
```

`register-server-task.ps1` carries the trigger, the SYSTEM principal and the
retry policy, and refuses to overwrite an existing task without `-Force` — so
re-running it cannot silently change a working schedule.

Use `git bundle`, not a working-tree copy: git performs the checkout so the
server's own line-ending rules apply, only tracked content travels, and no
GitHub credential is needed to obtain the code.

**Install nothing.** Python 3.12.10 (`C:\Python312`) and Git 2.55 are already on
this box from the steel-news deployment, and this project pins 3.12. The
deployment adds a folder, a venv, a task and a credential file — no new
software, which is why it needed no installation notice.

Keep the bundle in `C:\DataScienceProject\_installers\` so the deployment is
reproducible.

---

## Deployment record

| | |
|---|---|
| **Deployed** | 2026-08-02 |
| **Transport** | `git bundle` (48 MB), SHA-256 `8f84b0b4...65ea46e0`, verified at both ends |
| **Interpreter** | Python 3.12.10 (`C:\Python312`, pre-existing, deliberately off PATH) |
| **Dependencies** | `requests 2.34.2`, `beautifulsoup4 4.15.0`, `lxml 6.1.1`, `pandas 2.3.3`, `openpyxl 3.1.5`, `pytest 9.1.1` |
| **Test suite on the server** | **222 passed** — identical to the laptop baseline, and the first run of this codebase on 3.12.10 rather than 3.14.2. (213 at first deploy; 9 token-expiry tests added the same day) |
| **Line endings** | `quota_history_2026.csv` CRLF=9667 / bare-LF=0 on both hosts. `.gitattributes` pins it `-text`, so the blob is byte-identical everywhere regardless of `core.autocrlf` |
| **PATH** | Verified unchanged after deployment: `python` and `py` still resolve to 3.13.1 |
| **First inert end-to-end run** | 283 EU (0 failed), 75 UK (0 failed), 202 s |

### Target reachability, measured from this host 2026-08-02

Doc 00 of `meps-server-docs` is emphatic that "the server has internet" is not
validation, because bot-walls judge per site: from this same IP, `gmk.center`
returns 200 while `mining.com` returns 403. Tested with this project's
production User-Agent, against the URLs it actually fetches:

| Target | Result |
|---|---|
| EU TARIC quota detail (`quota_tariff_details.jsp`, real order numbers) | **200**, 54 KB, markup contains `Order number` and `Balance` |
| EU TARIC consultation page | **200**, 71 KB |
| UK Trade Tariff `quota_search` (real order numbers) | **200**, 80 KB, markup contains `Order number` and `Balance` |
| `raw.githubusercontent.com` published data | **200** |
| `api.github.com` | **200** |
| `pypi.org/simple` | **200** |

Both tariff sites are government services with no commercial incentive to run
bot protection, which is why this project migrated cleanly where the steel-news
scraper did not. **A pass today is not a permanent guarantee** — re-test if
scrapes start failing from this host but succeed elsewhere.
