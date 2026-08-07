# Session log — handover to the server (2026-08-07)

**Convention: this file is the *only* session log.** Each handover overwrites it;
older logs are deleted, not archived — history lives in git. It exists because
session context (decisions, in-flight threads, who is waiting on what) does not
travel with the code, and the work is moving from a laptop session to a Claude
Code session running directly on the company server.

**This repository is public.** People and infrastructure are deliberately
anonymised: colleagues appear by role, and there are no addresses, hostnames,
ticket numbers or security details here. The person-to-role mapping arrives via
the session kickoff prompt, not this file. Keep it that way in everything you
commit — see *Conventions* at the bottom.

---

## 1. State at handover — all verified

| | |
|---|---|
| Daily task | ✅ Healthy and unattended — data commits present for every day through 2026-08-07, pushed at ~05:43 each morning |
| Code on the server | ✅ Already current — the task's `git pull --rebase` step carried the webapp commits onto the server before this handover was written |
| Test suites | ✅ 327 passed (222 `tests/` + 105 `webapp/tests/`) at commit `b89e195`; `beta/` has its own 45 |
| Webapp | ✅ Built and verified against the real data locally; **not yet installed on the server** (see queue item 2) |
| Database | SQLite (`data/quota_tracker.db`, gitignored) — SQL Server switch approved, waiting on the database being created (queue item 3) |
| GitHub Actions | The freshness watchdog still runs there as the external heartbeat. Leave it — it is the "did data arrive today" check that does not depend on the server |

Recent non-data commits: `b89e195` (overview features + banding fix),
`a746bd1` (access/database analysis), `71d8fa2` (the webapp itself).

---

## 2. Decision of record: deliver the dashboard in Power BI

**2026-08-07.** The colleague who runs the SQL Server instance and the
company's reporting asked for the dashboard to be delivered **in Power BI**
rather than as a standalone website, to avoid parallel systems. Accepted — and
it resolves two open questions at once:

- **The database question.** The tracker was built on SQLAlchemy Core so the
  store is one connection string. The documented trigger for moving from SQLite
  to SQL Server was "a real Power BI need"; it has now fired, and it fired from
  the person whose permission the move needed. The CSV in `data/published/`
  remains canonical; the database stays a rebuildable projection either way.
- **The researcher-access question.** Power BI reaches researchers through
  their existing Microsoft accounts. The entire IIS reverse-proxy plan in
  `INTERNAL_SITE.md` — new site, DNS record, certificate, VPN-gated access,
  shared password — is **superseded**. Nothing from it needs building.

**The Flask site (`webapp/app.py`) is demoted to a local diagnostics tool.**
It keeps working against whichever database `QUOTA_DB_URL` points at and costs
nothing to keep, but nothing researcher-facing depends on it, so do not deploy
it behind IIS and do not spend effort polishing it.

What Power BI needs from our side, once the database exists: the `quota_daily`
table already carries denormalised `quota_year`, `quota_quarter`,
`quarter_start` and `day_in_quarter` columns precisely so report measures never
have to re-derive the Jul–Jun quota calendar. The pace/fastest-burning logic in
`webapp/queries.py` documents the intended measure definitions
(`pct_used / pct_elapsed`, exhausted excluded, bands on the displayed value).

---

## 3. Work queue, in order

1. **Verify the environment before changing anything.** `git status` clean,
   venv interpreter by full path (see `SERVER_DEPLOYMENT.md` — bare `python`
   is NOT ours on this machine), both test suites green, latest daily log in
   `data\logs\` shows a clean run.
2. **Install the webapp extras and load the database.**
   `<venv>\Scripts\python.exe -m pip install -r requirements-webapp.txt`, then
   `<venv>\Scripts\python.exe -m webapp.etl --rebuild`. Until this is done the
   daily task logs a WARN at its (deliberately non-fatal) ETL step; the next
   05:43 run should then show the step succeeding. That log line is the
   verification — no need to force a publish.
3. **Stage the SQL Server switch so it is one action when the database
   appears.** The instance owner is creating a database and a login for the
   account the daily task runs under. Prepare, but do not execute: the ODBC
   driver install (machine-wide → give notice first, though installs are
   generally approved), `pyodbc` into the venv, the `QUOTA_DB_URL` value (see
   `INTERNAL_SITE.md` for the shape), and a `--rebuild` against it. Migration
   loses nothing — the CSV is canonical.
4. **Power BI report.** Built in Power BI Desktop (not on this server) against
   the new database through the already-installed gateway; scheduled refresh
   ~06:30, after the 05:43 publish. Offer the instance owner either a finished
   report or the table/measure definitions, his choice.
5. **Process documentation for the company SharePoint** (being set up by the
   same colleague): a top-level write-up — problem statement, plain-English
   solution, architecture outline, where each piece runs. Distil from
   `ARCHITECTURE.md`, `INTERNAL_SITE.md` and `SERVER_DEPLOYMENT.md`; do not
   duplicate them, summarise them.

## 4. In-flight threads with people

- **The IT colleague** (runs the SQL Server, the hosting provider's firewall
  panel, and the backup/endpoint tooling): setting up the user's VPN access via
  an IT ticket; creating the Power BI database and task-account login; building
  the SharePoint documentation site. He has generally approved software
  installs on this box.
- **The research colleague** (owns dashboard content): three questions sent,
  answers pending — (a) is search by *steel grade* wanted, and can he supply
  the grade→category mapping, since it is not in the source data; (b) status
  thresholds 70/90 (the reference site's) vs our current 75/90; (c) are the
  reference site's import-history charts wanted eventually — different data
  source entirely, a project not a feature.
- **SSH from the user's laptop**: the home ISP rotates its address, which broke
  the per-address allow rule. The Windows-side rule is updated; the upstream
  (hosting-panel) rule is pending — the plan is to point it at the company
  VPN's fixed egress address once the user's VPN works. **None of this blocks
  server-side work any more**, since the session now runs on the server.

## 5. Built this session (already committed and pushed)

- Five overview features modelled on the reference tracker the research team
  named: days-left-in-quarter tile, fastest-burning callout, category count,
  `?pressure=1` category filter, `?sort=pressure|name` toggle.
- **Banding fix found via the rendered page, not tests**: bands were computed
  on raw percentages while the site prints one decimal, so a quota at 99.99%
  displayed "100.0%" under a tile labelled "75–99% used". Bands now use the
  displayed value; regression tests pin the boundary (99.99 → exhausted,
  99.94 → critical). Lesson repeated from the pace bug: anything the *view*
  computes needs a view-level check against the real render.
- SSH outage diagnosed (dynamic ISP address, not a server change) — see §4.

## 6. Server rules — non-negotiable

This is a live production machine (public API on IIS, SQL Server behind it,
Power BI gateway). Fuller detail in `SERVER_DEPLOYMENT.md`; the short version:

- **Never install anything that requires a reboot.** Check before running any
  installer.
- **Give notice before machine-wide installs** (the ODBC driver qualifies);
  per-project/venv installs are fine.
- **Treat `MSSQLSERVER`, the IIS sites and the gateway as read-only** until
  the instance owner has created our database — and even then, touch only ours.
- **The 05:43 daily task is the business-critical path.** Test with inert runs
  (`server-daily-task.ps1` without `-Push`); never leave it broken overnight.
- **The server's clock is authoritative** for anything date-gated. Do not
  reason from another machine's clock; earlier work found a laptop running
  minutes fast, and only the server decides when its tasks fire.
- **Three Python installs coexist here and bare `python` is not ours.** Always
  the venv interpreter by full path.
- **Antivirus races are a known failure mode**: intermittent
  `PermissionError`/`WinError 32` on `os.replace`/rename of a file your own
  code just wrote, succeeding on rerun ⇒ a scanner held the handle. Retry;
  do not debug your own code first.
- **Secrets live in `C:\DataScienceProject\_secrets\`**, outside every working
  copy, never committed.

## 7. Conventions

- **Public repo hygiene**: no credentials, no colleague names, no internal
  addresses/hostnames, no ticket or phone numbers, and no descriptions of the
  server's security posture in committed files. If continuation context needs
  such details, they go in the session prompt or a local uncommitted note.
- Documentation is **English only**.
- The published CSV is **canonical**; every database is a rebuildable
  projection of it. Nothing may make the publish depend on the database.
- Baseline the test suite before changing code; report honestly — anything not
  run is labelled UNVERIFIED, and failing tests are never weakened to pass.
- No destructive git (`reset --hard`, `checkout --`, `clean -f`) to escape a
  confusing state — stash or WIP-commit first.

## 8. What does not transfer automatically

The laptop session's memory directory and user-level preference file do not
travel with the repo. Their durable content is absorbed above (§6 clock rule,
§4 role map, §7 conventions). Person-to-role names arrive in the kickoff
prompt. If something seems missing, ask the user rather than guessing.
