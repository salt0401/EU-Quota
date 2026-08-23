# Session log — server session (updated 2026-08-22)

**Convention: this file is the *only* session log.** Each handover overwrites
it; older logs are deleted, not archived — history lives in git. It exists
because session context (decisions, in-flight threads, who is waiting on what)
does not travel with the code.

**This repository is public.** People and infrastructure are deliberately
anonymised: colleagues appear by role, and there are no addresses, hostnames,
ticket numbers or security details here. The person-to-role mapping arrives via
the session kickoff prompt, not this file. Keep it that way in everything you
commit — see *Conventions*.

---

## 1. State at handover — all verified on the server 2026-08-22

| | |
|---|---|
| Daily task | ✅ **Healthy.** 12 consecutive clean runs, 2026-08-10 → 08-21. `LastTaskResult 0`, 0 missed runs, next 06:40 local |
| Published data | ✅ `data_date 2026-08-21` — 16,468 rows, 46 days, 283 EU / 75 UK, 0 failed every day |
| History integrity | ⚠️ **One permanent gap, 2026-08-08**, unchanged. Every other day is complete at 358 rows |
| ETL step | ✅ Running inside the daily task and succeeding — the WARN that ran for weeks is gone |
| Tracker database | ✅ SQLite, refreshed daily by the task, 16,468 rows as of 08-21 |
| Interpreter | ✅ `venv\Scripts\python.exe` = Python 3.12.10. Bare `python` is 3.13.1 — not ours |
| Test suites | ✅ **327** (222 `tests/` + 105 `webapp/tests/`) + **45** in `beta/` |
| Deployment guards | ✅ `tools\assert-inert.ps1 -PostCutover` → exit 0 |
| IIS modules | ✅ **NEW 2026-08-22** — URL Rewrite 2.1 + ARR 3.0 installed, proxy enabled, live API verified unaffected |
| `waitress` | ⚠️ Installed, **not running**, and the startup task is **written but deliberately not registered** (`tools\quota-site-task.ps1`). It refuses to register while the site would serve unauthenticated |
| Site password | ⚠️ **NOT SET.** The app runs unauthenticated. This is the final step, by owner instruction |

**On the two clocks.** The trigger is **06:40 local**; the server runs
`GMT Standard Time`, currently BST (UTC+1), and logs stamp UTC — so a run starts
`05:40:02Z` and commits `05:43:45Z`. Anything date-gated reasons from **the
server's** clock, never another machine's. Note the corollary: between 00:00 and
01:00 local in summer the local and UTC dates disagree and a `-Push` run is
refused by design.

---

## 2. Decision of record: ship the internal site first, SQL Server + Power BI after

**2026-08-08, owner decision. This reverses the 2026-08-07 decision** that made
Power BI the delivery mechanism and marked the Flask site superseded.

The destination has not changed — the *order* has. Building a Power BI report
researchers find useful is slow while three content questions are still open
with the research colleague; the site already exists, is tested, and runs on the
server today. Put it in front of researchers, learn what they actually use, and
let that be the specification for the report.

> ### ⚠️ This is sequencing, not cancellation
> **The end state is still SQL Server as the store and Power BI as the
> researcher-facing dashboard.** The reasons have not changed: the gateway is
> already on this host, it cannot read SQLite, and quota data belongs alongside
> price data. **Trigger for migrating:** researchers confirm the site is useful,
> *or* the first request arrives for quota data alongside anything else in Power
> BI — whichever comes first.

**The objection, recorded honestly.** The instance owner asked for Power BI
*specifically to avoid parallel systems*, and standing this site up builds the
thing he asked to avoid. That is deferred, not answered. Two consequences, both
load-bearing:

1. **This site must not accumulate features that only exist here.** Anything
   researchers come to depend on has to be reproducible as a Power BI measure.
2. **The IIS work needs him anyway**, and it is a larger favour than creating a
   database was — so be straight with him about what it is for.

Full detail, including the migration checklist, is in `INTERNAL_SITE.md`.

---

## 3. Work queue, in order

> ### 🔑 THE LAST STEP, BY OWNER INSTRUCTION
> **`tools\set-site-password.ps1` is run LAST**, once everything else works, so
> that a password is not set and then forgotten while other work is in flight.
> **Until it is run the site is UNAUTHENTICATED**, so nothing may make it
> reachable from outside first — no proxy site, no `waitress` listening on
> anything but loopback, no DNS. Remind the owner when the rest is finished.

1. **Reply to the instance owner.** Two things: (a) the Power BI complications
   — feasible, needs the database, one modelling trap at the 90% boundary,
   slower iteration while exploring. **Licensing is NOT a complication**: every
   staff member already holds a licence via their Data Hub dashboard. (b) **ask
   for the database** — see §4. He also wants to test the app himself and has
   floated dropping Power BI if the app's interactivity is better, so an early
   look is worth offering.
2. **Chase the DNS record and certificate for `quota.meps.co.uk`.** He is
   arranging both through a colleague. **This is now the only external blocker**
   on researcher access. When they land:
   `tools\install-iis-reverse-proxy.ps1 -ConfigureSite`.
3. **Register the startup task.** `tools\quota-site-task.ps1 -Register`.
   **Written and tested 2026-08-23; deliberately not registered.** It runs
   `waitress` at boot on loopback via Task Scheduler as `SYSTEM` (no new
   software, same mechanism as the daily task, ports to the replacement VPS
   unchanged). **The tool refuses to register while the password file is
   absent**, so the ordering no longer depends on anyone remembering it —
   password first, then task, then start.
4. **NEW 2026-08-23: offline dashboard bundle** -- built and committed.
   `webapp/export.py` renders the site to static HTML (359 pages, 3.2 s, 2.1 MB
   zip), published to the `latest-data` release and extracted by the downloader.
   Renders the same templates through the same contexts as the live site, so it
   cannot drift; the >=90% band is carried as data rather than recomputed in
   JavaScript. Runs last in the daily task and is non-fatal. `download.py` is at
   2.10.0, so installed copies self-update. **Note: the release is public, so
   the presentation is now publicly downloadable -- owner decision, taken
   knowingly; the underlying numbers were already public on the same release.**
5. **Build the 90% work** (`TODO.md` §3): masthead count of quotas at or above
   90%, "crossed 90% on `<date>`" per quota, and a ≥90% filter. The highest-value
   content work, because 90% triggers a different customs process, and the
   crossing date is something the reference site cannot produce at all.
6. **The 2026-08-08 retry question — investigated 2026-08-23, and it cannot be
   answered retrospectively.** The reason the evidence is missing is not log
   rotation: the **`Microsoft-Windows-TaskScheduler/Operational` log is
   disabled** (`IsEnabled: False`, zero records retained). So Task Scheduler has
   never recorded whether it attempted the restarts. The absence of extra run
   starts in that day's script log only shows the *script* did not start again;
   it says nothing about whether the *scheduler* tried.
   **Task settings are unchanged and correct on paper** — `RestartCount = 2`,
   `RestartInterval = PT20M`, `ExecutionTimeLimit = PT1H` (that run took 21
   minutes, so it did not hit the limit).
   **Next step: enable that operational log**, which would make the next failure
   diagnosable. It is a system-level change, so it is **being asked for, not
   done** — see §4a. Until then, every transient source failure still risks a
   permanent one-day hole.
7. **Migrate to SQL Server** once the database exists. ODBC Driver 17 is already
   installed and the `NT AUTHORITY\SYSTEM` login already exists, so it is
   `pip install pyodbc`, set `QUOTA_DB_URL`, `--rebuild`.
8. **Power BI report**, built in Power BI Desktop (not on this server) against
   the SQL Server database through the existing gateway; refresh ~06:30, after
   the publish.
9. **Process documentation for the company SharePoint.** Distil from
   `ARCHITECTURE.md`, `INTERNAL_SITE.md`, `SERVER_DEPLOYMENT.md` — summarise,
   do not duplicate.
99. **LAST: set the site password** (see the box above).

## 4. In-flight threads with people

- **The IT colleague / instance owner** (runs the SQL Server, the hosting
  provider's firewall panel, the backup tooling): is building the SharePoint
  site, and is setting up the user's VPN access via an IT ticket.
  **2026-08-08:** accepted the site-first plan — *"Happy to go with your
  solution"* — while restating a preference for Power BI to avoid parallel
  systems. **2026-08-22:** approved the IIS installs outright — *"You are free
  to install the IIS add-ons"* — which unblocked and completed that work. He
  wants to **test the app himself**, and has raised the possibility of
  **dropping Power BI long term** if the app's interactivity turns out better.
  **He is arranging the DNS record and certificate** for `quota.meps.co.uk`
  through a colleague; that is now the only external blocker.

> ### ⚠️ CORRECTION 2026-08-22 — a commitment was attributed to him that he never made
>
> Earlier revisions of this file said he "owes the Power BI database and a login
> for the task account", and `INTERNAL_SITE.md` said he "offered a database" and
> "is creating these". **No message from him says any of that.** An earlier
> session appears to have turned *"he agreed to Power BI"* into *"he agreed to
> build the database"*, and every later session inherited it from this file
> rather than from the source.
>
> **True position: the database does not exist, he has probably never been asked
> for it, and he may not know one is needed. We are not blocked by him — we have
> simply not asked.**
>
> Kept rather than quietly deleted, because the failure mode is worth
> recognising: it was plausible, it was never checked against a primary source,
> and repetition made it look established. When this file states that someone
> has agreed to something, it should be traceable to something they wrote.

- **RESOLVED 2026-08-22 — the host is not the machine being retired.** The
  research colleague's *"reaching end of life ... replaced in the next few
  months"* referred to the **physical server in the MEPS office**. This project
  runs on a hosted VPS and is unaffected, so the IIS work was safe to do.
  Neither of the two readings we had considered was correct. **Separately, a
  replacement VPS is being provisioned** through MEPS's IT company — migration
  will be needed eventually, it is not urgent, and the box owner will give
  notice. That is why the IIS work is a re-runnable script.
- **The research colleague** (owns dashboard content): **all three questions
  answered 2026-08-08.** Grade search — not wanted, the team thinks in the
  broader categories. Import-history charts — not wanted, they receive trade
  data by another route (a fourth colleague is arranging that access).
  Thresholds — keep 75/90/100, **and 90% turns out to trigger a different
  customs process**, so it is an operational threshold rather than a colour. He
  also gave the audience size, ~15 people, and said Power BI *"would be good ...
  not critical"*. See `INTERNAL_SITE.md` for what this changes.
- **The user's VPN / SSH from the laptop**: an IT ticket, expected to progress
  after a call the week of 2026-08-10. Its egress address is what gets
  allowlisted for port 22. **This is the user's thread, not the agent's** — the
  session runs on the server and is not blocked by it.

## 4a. Asked, but NOT agreed — open requests to the instance owner

> **Read this heading literally.** Yesterday we found a commitment in these
> files that the instance owner had never made, produced by an earlier session
> turning "he agreed to X" into "he agreed to build X". This section exists so
> that never happens silently again. **Everything below is a request that has
> been drafted or sent. None of it has been agreed. Nothing here may be
> restated as approval without a message from him saying so.**

| # | What is being asked | Status |
|---|---|---|
| 1 | Permission to **create one small database** on the existing instance — SIMPLE recovery (inherited from `model`), with a size cap | **ASKED, not agreed** |
| 2 | Permission to create a **dedicated read-only login** for the Power BI gateway on that database — `db_datareader` only | **ASKED, not agreed** |
| 3 | Permission to **enable the Task Scheduler operational log** (a system-level setting) so run failures become diagnosable — see queue item 5 | **ASKED, not agreed** |
| 4 | The **DNS record and TLS certificate** for the tracker host name | **ASKED, he indicated he would arrange it; not yet delivered** |

**Why a dedicated read-only login rather than reusing something.** The
gateway's own service account has **no login on the instance at all**, so
"just let the gateway in as itself" is not available. A named, read-only,
single-database login is also the pattern the instance already uses elsewhere —
there are existing logins scoped to `db_datareader` on other databases — so this
asks for nothing unusual.

**What has actually been agreed, for contrast:** the IIS add-on installs
(*"You are free to install the IIS add-ons"*), and the site-first sequencing
(*"Happy to go with your solution"*). That is the complete list.

> **A company VPN may already exist** (requested via an IT ticket some weeks
> ago). Worth stating plainly, because it is easy to assume it solves more than
> it does: **a VPN existing does not by itself route anything through it.** The
> remote database sessions observed arrive directly from residential ISP
> addresses, so they currently bypass any VPN entirely. Making them use it is a
> client-configuration and policy change, not a consequence of the VPN being
> available. Not acted on — it is the owner's call and it is in the letter.

## 5. Session history

### 2026-08-22 — IIS front end installed; a fabricated commitment corrected

- **Verified two weeks of unattended running** before touching anything: 12
  clean runs 08-10 → 08-21, 46 days of history, one known gap, all suites green,
  all deployment guards passing. Nothing had drifted.
- **URL Rewrite 2.1 + ARR 3.0 installed** after the box owner approved it. The
  method matters more than the outcome and is preserved in
  `tools\install-iis-reverse-proxy.ps1`:
  - **The window was measured, not assumed.** IIS logs showed genuine API
    traffic confined to 02:00-15:00 UTC; 16:00-02:00 has had **3 successful
    requests in 14 days**. Installed at 23:28 UTC with 0 connections and
    0 requests/sec, no MEPS task due for 3.6 hours.
  - **The reboot question was answered before running an installer**, by reading
    each MSI's `InstallExecuteSequence` and `LaunchCondition` tables through the
    Windows Installer COM API. Neither schedules a reboot. Both then installed
    with `/norestart` and returned **exit 0, not 3010**, and the pending-file-
    rename queue was **3232 entries before and 3232 after** — we added nothing.
  - **The live API was proved healthy afterwards**, not merely "the site says
    Started": `/` returned 404 and `/v1/PriceAssessments` returned 401, matching
    its normal logged behaviour.
- **`-ConfigureSite` correctly refused** — no certificate for the host name, so
  it created nothing and exited non-zero. That is the boundary, working.
- **Read-only SQL Server reconnaissance** (see `INTERNAL_SITE.md`). We hold
  sysadmin, the `NT AUTHORITY\SYSTEM` login already exists, 150 GB free, `model`
  is SIMPLE. Nothing was created, altered or restarted.
- **Corrected a fabricated commitment** attributed to the instance owner — see
  the correction box in §4.

> **Noticed in passing, not ours:** the live API's certificate
> (`CN=api.mepsinternational.com`) **expires 2026-10-01**. It would take the
> public API down. Worth mentioning to the box owner.

### 2026-08-08 (all committed)

- **Environment verified** before anything changed (queue item 1 of the previous
  handover): git clean, correct interpreter, suites green, daily log clean.
- **Webapp installed and the database built** (previous queue item 2). Flask
  3.1.3 + SQLAlchemy 2.0.51 into the venv, `webapp.etl --rebuild` → 11,814 rows
  across 33 days, cross-checked against `metadata.json`. The incremental command
  the daily task actually runs (`python -m webapp.etl`, no `--rebuild`) was also
  exercised: exit 0, row count unchanged, confirming idempotency. `SYSTEM` has
  `FullControl` on the database file, which matters because the task runs as
  SYSTEM while it was created by Administrator.
- **`waitress` added** and verified serving the real data. `python -m webapp.app`
  is Flask's *development* server and is now documented as such.
- **`tools\set-site-password.ps1` written**, mirroring `set-github-token.ps1`.
- **Public-repo sanitisation.** The host address, hostname and SSH key name were
  committed in eight files; all are now placeholders resolved by a local
  uncommitted note beside the GitHub token. The worst instance was not a doc:
  the freshness watchdog embedded the SSH command in the heredoc it posts as a
  **GitHub issue body**, so every failure published the address publicly.
- **Repo reorganised**, stale docs pruned, dangling references fixed. See the
  commit message on `df4c7aa` for what moved and why.

### ⚠️ The daily task was broken, and is fixed

**`origin` had been changed to SSH** (`git@github.com:...`) at some point after
yesterday's successful run — `.git/config` was modified at 00:24 local, and an
SSH key appeared in the Administrator profile at 21:30 the evening before.

The task runs as **`SYSTEM`, which has no private key** — only `known_hosts`.
`ssh-agent` is Stopped and Disabled, and there is no `core.sshCommand` or
`GIT_SSH_COMMAND` override. Simulating SYSTEM's environment reproduced it
exactly:

```
git@github.com: Permission denied (publickey).
EXIT CODE = 128
```

Tomorrow's 06:40 run would have scraped, uploaded the release assets (the REST
API uses the token and is unaffected), committed — and then failed at
`git pull --rebase`. The fallback on the next line has no `-AllowFailure`, so
the script would have died **after committing and before pushing**, stranding
the day's data locally and firing the watchdog at 09:00 UTC.

**Fixed** by restoring the documented remote:

```powershell
git remote set-url origin https://github.com/salt0401/EU-Quota.git
```

That fix held and was confirmed in production: the 2026-08-09 run reached
`https://github.com/...` with the PAT, which is exactly the path it was supposed
to take.

### Incident, 2026-08-08 — source timeouts, one permanent day lost

262 of 283 EU quotas failed with `Read timed out` against `ec.europa.eu`; UK was
fine at 75/75. The publish gate refused, correctly:

```
RuntimeError: Refusing to publish: 262/283 EU quotas failed to scrape
```

**This is the guard working**, not a bug — publishing 21 of 283 quotas would
have filed a day that looks like mass quota expiry. The cause was transient; the
next day scraped cleanly.

**2026-08-08 is therefore a permanent hole in the history.** TARIC and the UK
tariff publish *current* balances, so that day cannot be re-scraped. Partial
output survives on disk in `data/output/2026-08-08/` (21 EU + 75 UK).
**Recommendation: leave the gap.** Backfilling a 96-row day into a 358-row
series would make 262 quotas look like they vanished for a day, which is worse
than an honest absence — anything consuming the history should treat a missing
date as missing, not as zero.

> **Follow-up worth taking: the retry policy did not visibly fire.** The task is
> configured `RestartCount=2`, `RestartInterval=PT20M`, and
> `SERVER_DEPLOYMENT.md` describes it as "retries twice, twenty minutes apart" —
> existing precisely to absorb a transient network failure like this one. The
> 2026-08-08 log contains **one** run start, not three. Either the restarts did
> not happen or they left no trace. Worth understanding, because had they fired,
> this day would probably have been saved.

### Incident, 2026-08-09 — push rejected for workflow scope (self-inflicted)

The scrape was clean; the push was rejected outright:

```
! [remote rejected] main -> main (refusing to allow a Personal Access Token to
  create or update workflow `.github/workflows/daily-quota-update.yml`
  without `workflow` scope)
```

**Cause: the sanitisation commit edited two files under `.github/workflows/`.**
The task's PAT is deliberately `Contents: Read and write` and nothing else, so
GitHub refused the whole push — including the data commit behind it. Colleagues
served 2026-08-07 data for two days.

**Resolved.** The workflow sanitisation was re-applied and pushed over SSH from
the Administrator account, so the remote and working copy now match; the task's
own pushes only ever stage `data/published/`, so the PAT is sufficient again.
Verified: `git diff origin/main -- .github/` is empty, and `data_date
2026-08-09` is live at origin.

Two lessons, both now in §6:

- **`git push --dry-run` cannot prove a push will be accepted.** It exercises
  connectivity and authentication; the workflow-scope rule is enforced
  server-side during the real ref update. A dry-run returned exit 0 before this
  failure.
- **Pushing by hand proves nothing about the task.** See the rule below.

## 6. Server rules — non-negotiable

This is a live production machine (public API on IIS, SQL Server behind it,
Power BI gateway). Fuller detail in `SERVER_DEPLOYMENT.md`; the short version:

- **Never install anything that requires a reboot.** Check before running any
  installer.
- **Give notice before machine-wide installs**; per-project/venv installs are
  fine. *(The ODBC driver turned out to be installed already, so the SQL Server
  migration no longer needs a notice.)*
- **Treat `MSSQLSERVER`, the IIS sites and the gateway as read-only** until the
  instance owner has acted — and even then, touch only ours.
- **The 06:40 daily task is the business-critical path.** Test with inert runs
  (`server-daily-task.ps1` without `-Push`); never leave it broken overnight.
- **Never leave the working tree dirty overnight.** *(New, learned tonight.)*
  The task runs `git pull --rebase`, which refuses outright with unstaged
  changes — verified, exit 128, `cannot pull with rebase: You have unstaged
  changes` — and the retry that follows is not fault-tolerant. The run would
  commit and then fail before pushing. Commit or stash before you stop.
- **`origin` must stay HTTPS.** *(See §5.)* The credential path is `GIT_ASKPASS`
  + the token file, which is HTTPS-only, and SYSTEM has no SSH key.
  `assert-inert.ps1` guards this — run it after touching git config.
- **Never commit a change under `.github/workflows/` from this machine's
  automation path.** *(New, 2026-08-09.)* The task's PAT has `Contents` only, by
  design, and GitHub rejects an entire push that modifies a workflow file
  without `workflow` scope — taking the day's data commit down with it. If a
  workflow genuinely must change, push it separately from the Administrator
  account (which goes over SSH, see below) and confirm the remote matches the
  working copy afterwards.
- **A successful manual push proves nothing about the scheduled task.**
  *(New, 2026-08-09.)* `C:\Users\Administrator\.gitconfig` carries
  `url."git@github.com:".insteadOf = https://github.com/`, so interactive
  pushes from that account are silently rewritten to **SSH** and authenticate
  with `id_ed25519`, bypassing the PAT and its scope limits entirely. SYSTEM has
  no such config and uses HTTPS + PAT. **Two accounts, two protocols, two
  credentials, same remote.** Verify the task's path by reading its log the next
  morning, not by pushing by hand.
- **`git push --dry-run` is not proof.** *(New, 2026-08-09.)* It validates
  connectivity and auth, not server-side policy such as the workflow-scope rule.
  It returned 0 immediately before the push that was rejected.
- **Measure the quiet window before touching IIS; do not assume one.**
  *(New, 2026-08-22.)* The API's real traffic is confined to roughly 02:00-15:00
  UTC and is invisible in raw request counts, because scanner noise dwarfs it —
  2,210 requests in a day of which **zero** were successful. Count **2xx
  responses**, not requests, and confirm with live counters immediately before
  acting.
- **This box already has a pending reboot, and has for a long time.**
  *(New, 2026-08-22.)* 163 days of uptime, `CBS RebootPending` set, and ~3,232
  queued file-rename operations — mostly printer-spooler cleanup, not a pending
  Windows Update. It is benign, but it means: pass `/norestart` to every
  installer, treat exit **3010** as a failure, and compare the pending-rename
  count before and after so you can prove you added nothing. It also means that
  if this box is ever rebooted, several thousand queued operations will run.
- **The server's clock is authoritative** for anything date-gated. Do not reason
  from another machine's clock.
- **Three Python installs coexist here and bare `python` is not ours.** Always
  the venv interpreter by full path.
- **Antivirus races are a known failure mode**: intermittent
  `PermissionError`/`WinError 32` on `os.replace`/rename of a file your own code
  just wrote, succeeding on rerun ⇒ a scanner held the handle. Retry; do not
  debug your own code first.
- **Secrets live in `C:\DataScienceProject\_secrets\`**, outside every working
  copy, never committed. That folder now also holds the server access note.

## 7. Conventions

- **Public repo hygiene**: no credentials, no colleague names, no internal
  addresses/hostnames, no ticket or phone numbers, and no descriptions of the
  server's security posture in committed files. If continuation context needs
  such details, they go in the session prompt or a local uncommitted note.
- Documentation is **English only**.
- The published CSV is **canonical**; every database is a rebuildable projection
  of it. Nothing may make the publish depend on the database.
- Baseline the test suite before changing code; report honestly — anything not
  run is labelled UNVERIFIED, and failing tests are never weakened to pass.
  Note that `webapp/tests` reporting "53 passed, 2 skipped" means the extras are
  missing and half the suite did not run — it is not a smaller suite passing.
- `docs/archive/` holds superseded material kept because it explains *why*
  something is the way it is. Nothing there is maintained; if it contradicts a
  document outside it, the outside document wins.
- No destructive git (`reset --hard`, `checkout --`, `clean -f`) to escape a
  confusing state — stash or WIP-commit first.

## 8. What does not transfer automatically

Person-to-role names arrive in the kickoff prompt, not here. The durable content
of any previous session's memory is absorbed above (§6 rules, §4 role map, §7
conventions). If something seems missing, ask the user rather than guessing.
