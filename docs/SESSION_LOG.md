# Session log — server session (2026-08-08)

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

## 1. State at handover — all verified on the server

| | |
|---|---|
| Daily task | ✅ Healthy — `LastTaskResult 0`, 0 missed runs, next run 06:40 local. **A break was found and fixed tonight, see §5** |
| Interpreter | ✅ `venv\Scripts\python.exe` = Python 3.12.10. Bare `python` is 3.13.1 — not ours |
| Test suites | ✅ **327** (222 `tests/` + 105 `webapp/tests/`) + **45** in `beta/`, all passing on the server |
| Webapp | ✅ **Installed and running on the server.** Extras in the venv, database built, `waitress` serving `/` and `/healthz` on `127.0.0.1:8081` |
| Database | SQLite at `data/quota_tracker.db` (gitignored), 11,814 rows / 33 days, matching `metadata.json` exactly |
| Deployment guards | ✅ `tools\assert-inert.ps1 -PostCutover` → **exit 0, all 12 guards pass** |
| GitHub Actions | The freshness watchdog still runs there as the external heartbeat. Leave it |

**On the two clocks.** The trigger is **06:40 local**; the server runs
`GMT Standard Time`, currently BST (UTC+1), and the logs stamp UTC — so a run
starts `05:40:02Z` and commits `05:43:45Z`. Earlier notes calling this "the
05:43 task" were quoting the UTC commit time. Same event, two clocks. Anything
date-gated reasons from **the server's** clock, never another machine's.

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

1. **Set the site password.** `tools\set-site-password.ps1` (written this
   session; prompts, no BOM, ACLs to SYSTEM/Administrators). **The site runs
   unauthenticated until this is done** — acceptable only while it is bound to
   `127.0.0.1`. This must happen *before* the IIS proxy exists, not after.
2. **Reply to the instance owner** — he asked a direct question and is waiting.
   Two things in one message: (a) what the Power BI complications actually are
   (feasible; needs the SQL Server database first, licence coverage for ~15
   users, one modelling trap around the 90% boundary, and slower iteration
   during the exploratory phase — which is the argument for site-first);
   (b) **the end-of-life question in §4.** Do not commission the IIS work
   before (b) is answered.
3. **Then ask for the IIS reverse proxy**, if (b) says the host has a future.
   The complete ask is in `INTERNAL_SITE.md` → *What to ask the box owner for*:
   URL Rewrite + ARR (machine-wide, **restarts IIS**, so confirm no reboot is
   required and schedule it), a DNS record, a certificate, and a new site on 443
   via SNI proxying to `127.0.0.1:8081`. **This is the only thing blocking
   researcher access.** Everything on our side is ready.
4. **Build the 90% work** (`TODO.md` §3): a masthead count of quotas at or above
   90%, a "crossed 90% on `<date>`" per quota, and a ≥90% filter. This is now
   the highest-value *content* work, because 90% turns out to trigger a
   different customs process — and the crossing date is something the reference
   site cannot produce at all, since it keeps no history.
5. **Keep `waitress` running across a reboot.** A scheduled task with an
   `At startup` trigger needs no new software. Not built yet.
6. **Migrate to SQL Server** when §2's trigger fires. Staged and cheap: the ODBC
   driver is **already installed** (verified — no machine-wide install, no
   notice needed), so it is `pip install pyodbc`, set `QUOTA_DB_URL`, `--rebuild`.
7. **Power BI report**, built in Power BI Desktop (not on this server) against
   the SQL Server database through the existing gateway; scheduled refresh
   ~06:30, after the publish. Offer the instance owner either a finished report
   or the table/measure definitions, his choice.
8. **Process documentation for the company SharePoint**: problem statement,
   plain-English solution, architecture outline, where each piece runs. Distil
   from `ARCHITECTURE.md`, `INTERNAL_SITE.md`, `SERVER_DEPLOYMENT.md` — do not
   duplicate them.

## 4. In-flight threads with people

- **The IT colleague / instance owner** (runs the SQL Server, the hosting
  provider's firewall panel, the backup tooling): owes the Power BI database and
  a login for the task account; is building the SharePoint site; has generally
  approved software installs. **Now also the blocker on the IIS proxy** (queue
  item 2). He is setting up the user's VPN access via an IT ticket.
  **2026-08-08:** accepted the site-first plan — *"Happy to go with your
  solution"* — while restating a preference for Power BI to avoid parallel
  systems, and asking directly what the complications of Power BI would be.
  **Two things are owed to him:** that answer, and a resolution of the
  end-of-life question below.

- **OPEN QUESTION — is this host being replaced?** The research colleague wrote,
  of hosting the site, *"this is reaching end of life soon so will be replaced
  in the next few months."* **Which machine he means is not established** — this
  host, or a separate on-premises internal server. He is not IT, so ask the
  instance owner, who owns the hardware. **Resolve before commissioning the IIS
  work**: if it is this host, that work buys a few months and the deployment
  inherits a migration, whereas Power BI Service would survive a server
  replacement with only the gateway and database to re-home.
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

## 5. Done this session (2026-08-08, all committed)

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

Verified: anonymous fetch works, and `push --dry-run` with the token through
`GIT_ASKPASS` returns exit 0. `assert-inert.ps1 -PostCutover` now passes all 12
guards. **If SSH access from this box to GitHub is wanted, it must not be on
`origin`** — use a second remote, or the task loses its credential path.

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
- **`origin` must stay HTTPS.** *(New, see §5.)* The credential path is
  `GIT_ASKPASS` + the token file, which is HTTPS-only, and SYSTEM has no SSH
  key. `assert-inert.ps1` guards this — run it after touching git config.
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
