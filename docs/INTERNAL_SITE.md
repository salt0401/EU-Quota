# Internal quota tracker — design and deployment

An **internal** website for MEPS researchers showing EU and UK steel quota
usage, grouped by product category, with per-quota daily history.

> **This is not the customer-facing MEPS website**, and it is not a step towards
> it. Changes to the customer site are on hold because of contractual issues
> with the current provider (colleague, 2026-08). Nothing here is exposed to
> customers, and the page says so in its own header.

---

## Status

| | |
|---|---|
| **Built and tested** | ✅ 105 tests, verified against the real published history |
| **Code on the server** | ✅ Arrives by itself — the daily task runs `git pull --rebase` before it pushes |
| **One-off setup done** | ✅ **2026-08-08** — extras installed in the venv, database built (11,814 rows), ETL verified. Password file still outstanding |
| **Database** | SQLite, on the server, loaded and refreshed by the daily task. SQL Server remains the **eventual** target — see *The database plan* |
| **IIS modules** | ✅ **2026-08-22** — URL Rewrite 2.1 and ARR 3.0 installed, proxy enabled, live API verified unaffected |
| **Reachable by researchers** | ⏳ Not yet — blocked on the DNS record and certificate for `quota.meps.co.uk`, and on the site password |

> **SSH being down does not block this.** `tools/server-daily-task.ps1` runs
> `git pull --rebase origin main` before pushing, so anything merged to `main`
> lands on the server the next morning with no action from anyone.

**Verified on the server, 2026-08-08:** `python -m webapp.app` serves `/` (195 KB
of real HTML) and `/healthz` on `127.0.0.1:8081`, against 33 days of published
history. What is missing is not the application — it is the route to it.

> ### ⚠️ The site is UNAUTHENTICATED until the password file exists
>
> `tools\set-site-password.ps1` has deliberately **not** been run yet — it is
> the last step, so the password is set once everything else works rather than
> being set and forgotten mid-build. Until then the app starts without auth and
> says so on stdout.
>
> **Therefore: nothing may make this reachable from outside before that.** The
> IIS modules are installed but no proxy site exists, `waitress` is not running,
> and `quota.meps.co.uk` does not resolve. Any one of those changing without the
> password in place would expose an unauthenticated site.

---

## Decision of record: ship this site first, move to SQL Server + Power BI after

**2026-08-08, owner decision. This reverses the 2026-08-07 decision that made
Power BI the delivery mechanism and marked this site superseded.**

### What changed

Nothing about the *destination* — it is the *order* that changed. Building a
Power BI report that researchers actually find useful is slow: it needs the
database created, the gateway pointed at it, measures written, and a report
designed for people whose requirements are still three open questions. This
site already exists, is tested, and runs on the server today.

So: **put this in front of researchers first and learn what they use.** Whatever
they actually reach for is the specification for the Power BI report — a far
better specification than one written before anyone has seen the data.

### ⚠️ This is a sequencing decision, not a cancellation

**The end state is still SQL Server as the store and Power BI as the
researcher-facing dashboard.** If you are reading this months later wondering
why the tracker is a Flask app: it was a deliberate first step, and finishing
the migration is outstanding work, not an abandoned idea. The reasons SQL Server
wins have not changed — the gateway is already on this host, it cannot read
SQLite, and quota data belongs alongside price data.

**The trigger for migrating:** researchers confirm the site is useful, *or* the
first request arrives for quota data alongside anything else in Power BI.
Whichever comes first. Migration is a connection-string change plus
`--rebuild`; nothing is lost, because the CSV is canonical.

`SESSION_LOG.md` carries this in its work queue so it stays visible.

### Both stakeholders have now agreed to this (2026-08-08)

It began as a unilateral reversal. It is not one any more — both people whose
opinion it depends on replied the same day, and both accepted, from opposite
directions:

- **The research colleague** (owns the content): Power BI *"would be good to
  have ... however this is not critical. If it is difficult or costly to
  implement then the website would be sufficient."*
- **The instance owner** (owns the box and the reporting estate): *"No problem
  about your proposed solution ... Happy to go with your solution, but to avoid
  having different systems it would be convenient to add this dashboard to
  Power BI."*

So: build the site, use it to find out which views matter, then port those to
Power BI. Nobody is being overruled — but the instance owner's preference is
explicit, and the second half of the plan is what honours it.

### The objection, still live

He asked for Power BI **specifically to avoid parallel systems**, and standing
this site up builds the thing he would rather not have. He has agreed to it;
that is not the same as the concern going away. It is *deferred*, on the
understanding that this site is an evaluation with a defined end, not a second
permanent system. Two consequences, both load-bearing:

1. **Do not let this site accumulate features that only exist here.** Anything
   researchers depend on has to be reproducible as a Power BI measure — now
   including the 90% threshold, which has an operational meaning and must land
   on the same boundary in both systems.
2. **The IIS work needs him anyway** — see *How researchers reach it* — and it
   is a larger favour than creating a database was.

> ### ✅ Resolved: the host is NOT the machine being retired
>
> The research colleague wrote, of hosting the site, *"this is reaching end of
> life soon so will be replaced in the next few months."* We could not tell
> which machine he meant and flagged it as a risk to the whole IIS plan.
>
> **Answered 2026-08-22: he meant the physical server in the MEPS office.** This
> project runs on a hosted VPS, which is unaffected. The IIS work is therefore
> not being spent on a machine about to disappear, and it went ahead.
>
> Worth keeping the episode: the concern was legitimate and correctly stopped us
> committing the box owner's time, but the answer was different from either
> reading we considered. Neither guess was right, and asking cost one sentence.
>
> **Separately, and genuinely: a replacement VPS is being provisioned** through
> MEPS's IT company. Migration will be needed eventually. It is not urgent and
> the box owner will give notice — but it is why
> `tools\install-iis-reverse-proxy.ps1` exists as a re-runnable, idempotent
> script with pinned payload hashes rather than a list of commands someone
> types twice.

---

## What it shows

The main view groups quotas by **product category**, most-pressed category
first, and shows for each quota exactly the fields that were asked for:

| Requested | Column |
|---|---|
| product category and quota order number | category is the group heading; order number links to the detail view |
| country or residual allocation | `Country / allocation` — residual rows read `Other countries`, `FTA Quota – Other` |
| current quota limit | `Quota limit (t)` |
| quantity allocated | `Allocated (t)` |
| quantity remaining | `Remaining (t)` |
| percentage used | `% used`, with a bar and a colour band |
| last update date and time | in the header — the **source scrape time**, not the page-load time |

Plus `Awaiting (t)` for EU quotas, which was not requested but decides whether a
quota is *really* open early in a quarter: pooled requests can exceed the whole
quota before allocation happens.

The drill-down view (`/quota/<region>/<order_number>`) shows quarter-to-date
usage as a chart — cumulative % used as a line, tonnes taken each day as bars,
and a dashed **pace line** showing how far through the quarter we are. Above the
line means the quota is being consumed faster than the calendar. Under it is the
full daily movement table including a `Used that day (t)` column, because
"how quickly is it being used" is the day-over-day delta; a cumulative line
alone hides a quota that took 80% in three days.

### The quota limit is never recomputed

It is stored and displayed exactly as published. Any rollover between periods is
already reflected upstream by TARIC and the UK tariff, and re-deriving it here
would risk disagreeing with the authoritative figure. The tracker's job is to
reflect it accurately, not to calculate it.

### The quota year is July–June

Q1 Jul-Sep · Q2 Oct-Dec · Q3 Jan-Mar · Q4 Apr-Jun.

This is **not** the same as the calendar quarters in `src/config.py`, which
exist to build the `StartDate` parameter TARIC expects. Both are correct for
their own job; conflating them is the obvious way to get this wrong, so they
live in separate modules and neither imports the other.

Every row is stamped with `quota_year`, `quota_quarter`, `quarter_start` and
**`day_in_quarter`**. That last one is what makes "compare the same point in
different quarters" possible — raw dates cannot do it, because quarters have
different lengths and start on different weekdays. Day 33 of Q1 and day 33 of Q2
are directly comparable.

History is retained from **1 July 2026**, the regime boundary. Nothing earlier is
loaded: the previous EU safeguard had 189 quotas with different order numbers and
volumes, so mixing it in would make category groupings meaningless.

---

## Architecture

```
daily scheduled task (existing)
  run.py --publish
    -> data/published/quota_history_<YEAR>.csv   <- CANONICAL, git-tracked
    -> data/published/metadata.json
         |
         |  python -m webapp.etl        (non-fatal step in the same task)
         v
  quota_daily table  (SQLite or SQL Server)      <- DERIVED read model
         |
         v
  webapp/app.py (Flask)  ->  internal site
```

**The database is a derived read model, not the system of record.** Two
consequences, and they are the whole reason for the shape:

1. A database outage, a permission change or a migration **cannot break the
   daily publish**. `src/` does not import `webapp/`, and the ETL step in
   `tools/server-daily-task.ps1` is explicitly non-fatal — by the time it runs,
   the data is already committed and uploaded, so colleagues have what they need.
2. Nothing in the database exists nowhere else. Anything wrong is fixed by
   `python -m webapp.etl --rebuild`.

The ETL is idempotent: every date in the CSV is deleted and re-inserted, so
re-running converges instead of duplicating. That mirrors the daily publish
itself, which replaces history rows per `(date, region)` rather than appending.

---

## Two things that need someone else

### 1. Where the database lives — *the database plan*

The colleague asked for SQL, and MEPS already runs **SQL Server 2022** on this
host — which is also the natural home if researchers later want Power BI on this
data, since the gateway is already there.

But `meps-server-docs` is explicit: *"Do not touch the existing `MSSQLSERVER`
instance. It backs a live public API. Ask before creating anything on it."* That
is a permission question, not a technical one.

So the code targets SQL Server and runs on SQLite, and the choice is one
environment variable:

```
QUOTA_DB_URL=sqlite:///C:/DataScienceProject/EUQuota/data/quota_tracker.db
QUOTA_DB_URL=mssql+pyodbc://@localhost/MEPSQuota?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
```

| | SQLite | SQL Server |
|---|---|---|
| Permission needed | none | ⚠️ ask the box owner |
| Extra install | none | `pyodbc` + an ODBC driver |
| Adequate at this volume? | **yes** — 358 rows/day, ~131k/year | yes |
| Coupled to the production instance | no | yes — shares it with the live API |
| Power BI / other consumers | no | **yes** |
| Backed up by the existing job | not needed — see below | yes |

**Update 2026-08-07: SQL Server, at the instance owner's own request.** He asked
for the dashboard to be delivered in Power BI. That is the whole of what he
said — see the correction below.

> ### ⚠️ Correction 2026-08-22: he was never asked for a database
>
> Earlier revisions of this file and of `SESSION_LOG.md` stated that the
> instance owner "offered a database" and "is creating the database and a login
> for the task account", and that we were waiting on him for it. **No message
> from him says any of that.** The claim appears to have been produced by an
> earlier session turning "he agreed to Power BI" into "he agreed to build the
> database", after which it was repeated as established fact.
>
> **The true position: the database does not exist, he has probably never been
> asked for it, and he may not know we need one.** We are not blocked by him;
> we simply have not asked. Nothing here is his fault or his omission.
>
> Recorded rather than quietly deleted, because a fabricated commitment
> attributed to a colleague is a specific kind of error worth being able to
> recognise again: it was plausible, it was never verified, and it survived
> because every later session inherited it from the file rather than the
> source.

**Update 2026-08-08: running on SQLite for now, SQL Server still the target.**
The sequencing decision above puts the Flask site in front of researchers first,
and that site runs perfectly well on SQLite at this volume. The permission is
granted and the offer stands, so the migration is *staged and waiting*, not
blocked:

| Step | State |
|---|---|
| ODBC Driver 17 for SQL Server | ✅ **already installed** (64-bit) — verified 2026-08-08, so no machine-wide install and no notice needed |
| `pyodbc` in the venv | ⏳ one `pip install`, venv-local |
| The database itself | ⏳ **not created, and not requested.** We hold sysadmin on the instance so we *could* create it; the standing rule is to ask first. See *Do we need to ask?* below |
| Login for the task account | ✅ **already exists** — `NT AUTHORITY\SYSTEM` has had a login on this instance since 2024-12-11. Only database-level permissions would be needed, not a new login |
| `QUOTA_DB_URL` → SQL Server | ⏳ one environment variable |
| `--rebuild` against it | ⏳ under a minute |

That is the whole migration. It stays one action whenever it is wanted.

### Do we need to ask? Reconnaissance of 2026-08-22

Read-only investigation of the local instance, run because the answer decides
how the request to the box owner is worded. **Nothing was created, altered or
restarted** — every statement was a `SELECT`, issued through
`System.Data.SqlClient` with Integrated Security so nothing had to be installed.

| Question | Answer |
|---|---|
| Can we connect? | **Yes**, as the local Administrator account |
| Are we sysadmin? | **Yes** — and `dbcreator`, `securityadmin`, `serveradmin`, and `CREATE ANY DATABASE` |
| Version / edition | SQL Server 2022 **Express Edition**, 16.0.1170.5 RTM |
| Databases present | 9 (4 system + 5 application). Ours would be the 10th |
| `model` recovery model | **SIMPLE**, so a new database inherits SIMPLE — no log-backup chain to maintain, which is exactly right for a rebuildable projection |
| Default data path | `C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQL\DATA\` |
| Free space on that volume | **150.2 GB free of 239.5 GB** — our database would be tens of MB |
| Login for `NT AUTHORITY\SYSTEM`? | **Already exists**, enabled, created 2024-12-11 |
| Power BI gateway | `PBIEgwService`, **Running**, automatic start, as `NT SERVICE\PBIEgwService` |

**So the technical answer is: we could create it ourselves, today, and it is a
smaller job than assumed** — the login the daily task would use already exists,
so only database-level permissions would be needed, not a new login.

**The governance answer is: ask anyway.** The standing rule quoted above —
*"Do not touch the existing `MSSQLSERVER` instance. It backs a live public API.
Ask before creating anything on it"* — is a permission question, and having
sysadmin is precisely why it is worth honouring rather than a reason to skip it.

The useful consequence is that the request is small and specific: *may I create
one small database on the instance*, not *please build us a database and a
login*.

Three things found on the way that are worth knowing:

- **Express Edition** caps a database at 10 GB and provides no SQL Server Agent.
  Neither binds us — the history is ~131k rows/year, and the ETL is driven by
  the Windows scheduled task, not an Agent job. Express is a supported gateway
  source. But Express also caps the buffer pool at roughly 1.4 GB, and the
  existing databases already total about 1.1 GB of data files. Our working set
  is small, so the added memory pressure is marginal — not zero, and worth a
  sentence when asking, because the instance backs a live API.
- **The gateway's service account has no SQL login.** `NT SERVICE\PBIEgwService`
  is not among the instance's logins, so when a Power BI data source is
  configured it will need explicit credentials rather than passing through as
  its service account.
- **The live API's certificate expires 2026-10-01.** Unrelated to this project
  and not ours to renew, but noticed while checking the certificate store, and
  it would take the public API down.

The original reasoning, kept for the record:

The usual objections do not survive contact with this project:

- **Concurrency** — one writer (the daily ETL), a few readers. In WAL mode
  readers never block. This is SQLite's ideal workload, not a compromise.
- **Backup** — normally the strongest argument for SQL Server, and here it
  evaporates. The CSV is canonical and replicated to GitHub. Losing the database
  file costs one `--rebuild`, under a minute.
- **"Connected to SQL"** — the requirement was retaining daily snapshots for
  historical comparison, not a particular product. SQLite *is* SQL.

**The one thing that decides against it is Power BI.** The gateway is already on
this server pointing at SQL Server and cannot read a SQLite file. The moment
anyone wants quota data in Power BI alongside price data, SQL Server wins
outright. **That is the trigger — not a date, and not a row count.** Migration
is a connection-string change plus `--rebuild`; nothing is lost, because the CSV
is canonical.

> **Host-specific caveat.** Two real-time file scanners run on this host with no
> path exclusions, and either can hold a handle on a file just after it is
> written. If the ETL ever fails with `WinError 32` on the database file, that is
> the cause — not the code — and re-running will succeed.

### 2. How researchers reach it

> **Reinstated 2026-08-08.** Briefly marked superseded when Power BI was to be
> the delivery mechanism; the sequencing decision above puts this back on the
> critical path. **This is now the one thing blocking researcher access.**

The server is **standalone in `WORKGROUP`, not on `meps.local`** — there is no
internal LAN path to it. Everyone, including researchers, reaches it over the
internet. So "internal" here means *authenticated*, not network-isolated.

**These are two independent decisions**, and conflating them is what made this
look harder than it is:

#### (a) The network path

Port **443 is already open in both firewalls** (verified 2026-08-05). A route
that reuses it needs **no firewall change at either layer**, which removes the
hosting provider's account holder from the picture permanently.

| Route | Cost | Who is needed |
|---|---|---|
| **New IIS site on 443**, own hostname via SNI, reverse-proxy to Flask on loopback | URL Rewrite + ARR install **restarts IIS — seconds of downtime on the live API** — plus a DNS record and a certificate | box owner, with notice |
| New port served directly by `waitress` | new port in **both** firewalls; TLS handled in Python | ⚠️ hosting provider's account holder, repeatedly |
| Path under the existing hostname (`/quota`) | no DNS or certificate, but edits the **production** site's config | box owner; highest blast radius |
| SSH tunnel | none | nobody — unusable for non-technical users |

**Take the first.** A one-time, schedulable IIS restart buys permanent
independence from the account holder, and adding a *new site* is far safer than
editing the live one. Confirm the modules install without a **reboot** first —
nothing requiring a reboot can go on this box.

#### What to ask the box owner for

This is the whole ask, in one place, so it can be forwarded as-is. **None of it
has been done — IIS is untouched, per the read-only rule.**

| # | Ask | Why it needs him | Risk |
|---|---|---|---|
| 1 | ~~Install **URL Rewrite 2.1** and **Application Request Routing 3.0**~~ | — | ✅ **DONE 2026-08-22.** He approved it (*"You are free to install the IIS add-ons"*). Installed in a measured quiet window; both returned exit 0, not 3010; the live API was serving again immediately afterwards |
| 2 | A **DNS record** for an internal hostname pointing at this host | He runs DNS | None |
| 3 | A **TLS certificate** for that hostname, bound via SNI on 443 | Certificate issuance | None — SNI means the existing site keeps its own binding |
| 4 | A **new IIS site** bound to that hostname, reverse-proxying to `127.0.0.1:8081` | IIS administration | Low — a *new* site, not an edit to the live one |

Everything on our side of that boundary is ready: the app runs, the database is
loaded, `waitress` is installed to serve it properly rather than through Flask's
development server, and the IIS modules are in place with the proxy enabled.

`tools\install-iis-reverse-proxy.ps1 -ConfigureSite` will create the site, bind
the certificate and write the rewrite rule in one step — it **refuses** while no
certificate for the host name exists, which is where it stops today.

**Before it is exposed, the password file must exist** (see *Authentication*).
The app runs unauthenticated without it and says so on startup — harmless on
loopback, unacceptable on 443.

#### (b) Who is allowed in

| Mechanism | Constraint enforced | Works from home? | Effort |
|---|---|---|---|
| IP allowlist | *location* | ❌ no | low, then constant |
| Password over HTTPS | *knows a secret* | ✅ yes | trivial — built |
| **Client certificate (mTLS)** | ***the device*** | ✅ yes | one cert per desktop |
| Entra/M365 SSO via outbound tunnel | *company identity* | ✅ yes | tenant admin + DNS |

> **Do not IP-allowlist researchers.** They work hybrid — two days a week from
> residential connections whose addresses change without warning. It recreates
> the port-22 firewall treadmill, but for a dozen people instead of one.

"Company desktop only, from any location" is buildable, and **client
certificates are the mechanism**: IIS rejects a machine without one at the TLS
handshake, before the request ever reaches Flask. Authentication inside the
application can only reject requests the application has already parsed;
authentication at the edge means unauthorised traffic never touches our code —
which matters on a production host. The dependency is whether
company desktops are Intune/GPO-managed, so IT can push the certificate
centrally. **One question to IT decides this.**

**Start with the password anyway.** The quota balances are *already public* —
TARIC and the UK tariff publish them, and the TrueNorth site shows the same
numbers to anyone. What is internal here is MEPS's framing, not the figures.
Certificate infrastructure to protect public data is the wrong trade; ship with
a password over HTTPS and add mTLS later if it is cheap.

Until deployed the app binds to `127.0.0.1` by default, deliberately: this host
runs production services, and nothing here should widen its surface by
accident.

### Authentication

HTTP Basic, password read from
`C:\DataScienceProject\_secrets\quota-site-password.txt` (same convention as the
GitHub token — outside every working copy, ACL'd). If the file is absent the app
runs **unauthenticated** and says so loudly on startup, which is fine bound to
`127.0.0.1` and not fine otherwise.

Set it with **`tools\set-site-password.ps1`**, which prompts (so the password
never reaches a command line or a shell history), writes UTF-8 with no BOM, and
ACLs the file to `SYSTEM` and `Administrators`. The BOM detail is not
decoration: `app.py` reads the file as UTF-8, so a BOM would silently become
part of the password and every login would fail with nothing useful in the log.
Windows PowerShell 5.1 writes one by default from `Set-Content` and `Out-File`
alike, which is why the script uses .NET directly — the same trap that
`set-github-token.ps1` exists to avoid.

**The password is read at startup, not per request.** Restart `waitress` after
changing it.

**Status 2026-08-08: not set.** The site therefore runs unauthenticated today,
which is acceptable only because it is bound to `127.0.0.1`. This must be done
before the IIS proxy is created, not after.

A password makes the site useless to a passer-by; it is not a substitute for
restricting who can reach the port. Do both, or neither is worth much.
`/healthz` stays open so a monitor does not need the password.

---

## Running it

On the company server the first two steps are **already done** (2026-08-08).
They are listed for a fresh machine, or after a venv rebuild:

```bash
# one-off: install the extras into the venv (NOT in requirements-ci.txt)
venv\Scripts\python.exe -m pip install -r requirements-webapp.txt

# load the database from the published history
venv\Scripts\python.exe -m webapp.etl --rebuild
```

Serving — **use `waitress`, not `python -m webapp.app`**. The latter is Flask's
development server, which prints its own warning and is single-threaded:

```bash
venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8081 --call webapp.app:create_app
```

`python -m webapp.app` stays useful for a quick look with `--no-auth`, and
nothing else.

Set the password before exposing it beyond loopback:

```bash
powershell -ExecutionPolicy Bypass -File tools\set-site-password.ps1
```

The daily task refreshes the database automatically after each publish. Pass
`-SkipEtl` to `server-daily-task.ps1` to suppress that.

> **Still to do before researchers can reach it:** the password file, the IIS
> reverse proxy (see *What to ask the box owner for*), and something that keeps
> `waitress` running across a reboot — a scheduled task with an `At startup`
> trigger is the low-ceremony option and needs no new software, but it has not
> been created yet.

### Tests

```bash
<venv>\Scripts\python.exe -m pytest webapp/tests -q     # expect 105 passed
```

Both suites together are **327** (`tests` 222 + `webapp/tests` 105), verified on
the server 2026-08-08. If `webapp/tests` reports "53 passed, 2 skipped" the
extras are not installed — the two heaviest modules skip at collection, which is
easy to misread as a smaller suite passing rather than most of it not running.

They use synthetic CSVs and temporary SQLite files — no network, no server, no
committed data. They skip cleanly if the webapp extras are not installed, so
`pytest tests/` on the server is unaffected.

---

## Deliberately not built

- **No write path.** The site is read-only. Nothing a researcher clicks can
  change quota data, so it can never disagree with the published history.
- **No CDN, no npm, no build step.** Server-rendered HTML and a ~90-line vanilla
  SVG chart. The site must still work in five years without anyone
  reconstructing a toolchain, and an internal tool that cannot reach a CDN
  should not degrade.
- **No forecasting.** `beta/` covers that and is deferred separately; this shows
  what happened, not what will.
- **No email or alerting.** The existing freshness watchdog already covers "did
  the data update", and a second alerting path would be a second thing to
  maintain.

---

## Measured against the reference site

The colleague named a model: TrueNorth Engineering's *Free Steel Quota Tracker*
(UK balances). Read 2026-08-05. It is more useful than the requirements list,
because it shows what "good" looks like to him.

The two hardest things to build, we already have: the **pace metric** (usage
speed against elapsed time) and **status bands**. We also carry things it does
not — it is UK-only, so no EU quotas, no awaiting-allocation, and no per-quota
daily drill-down.

| TrueNorth has | Status |
|---|---|
| Days remaining in the quarter, headline | ✅ built — masthead tile, measured from the data date |
| **Fastest-burning quota line** | ✅ built — see the ranking note below |
| Count of categories tracked | ✅ built — counted per `(region, category)`, so it equals the sections on the page |
| One-click "under pressure" filter | ✅ built — `?pressure=1`, filters whole categories |
| Sort toggle: most-used vs category order | ✅ built — `?sort=pressure\|name` |
| Bands at 70 / 90 | ✅ **answered 2026-08-08 — keep 75 / 90 / 100.** See the note below: 90 is not cosmetic |
| **Search by steel grade** (EN3B, 304, S355) | ❌ **answered 2026-08-08 — not wanted.** "Please disregard the grades. The research team will mainly think in these broader categories." No grade→category map is needed, and the one capability the reference site had over us is deliberately declined |
| 12-month import history, YoY, 3-month weighted average | ❌ **answered 2026-08-08 — not wanted.** The research team already receives historical trade data through another route. Trade-flow ingestion is off the roadmap entirely |

### The three open questions are now closed (2026-08-08)

All three were answered by the research colleague in one reply. Two removed
work; the third added a requirement that was not previously visible.

> ### ⚠️ 90% is an operational threshold, not a colour
>
> *"75% and 90% work for me. **The 90% is the key indicator as it triggers a
> slightly different customs process.**"*
>
> This changes what the number is **for**. 75% is advisory — a quota worth
> watching. **90% is a state change in someone's actual job**: past it, imports
> against that quota go through a different customs process. It should not be
> merely one of three colours in a legend.
>
> Consequences worth building toward, none of them yet built:
>
> - A **count of quotas at or above 90%** deserves masthead prominence, next to
>   the exhausted tile — it is the number with an operational consequence.
> - **"Crossed 90% on <date>"** is computable exactly, because the daily history
>   is per-quota per-day. The reference site cannot do this; it has no history.
>   This is a stronger differentiator than grade search would have been.
> - A filter for "at or above 90%" is more useful than the current
>   `?pressure=1`, which filters whole categories.
> - **Any Power BI port must reproduce the 90% boundary exactly**, including the
>   displayed-value rounding rule below. A quota printing "90.0%" must be on the
>   same side of the line in both systems, or the two disagree about whether a
>   customs process applies.

### Audience size: ~15 people

The research and analysis teams, per the same reply. Two things follow:

- **A single shared password is thin for 15 people** — no revocation for one
  person, and it spreads. It is fine for an evaluation, and it is what is built.
  If the site outlives the evaluation, revisit the mTLS/SSO options above.
- **Power BI licensing is a non-issue** (confirmed 2026-08-22): every staff
  member already holds a licence through their existing Data Hub dashboard, so
  the ~15 users cost nothing extra and no procurement step stands in the way.

### "Burning fastest" is ranked by pace, not tonnage

`pct_used / pct_elapsed`, so 2.0 means "consuming its allowance twice as fast as
the quarter is passing". Ranking by tonnes per day was the obvious alternative
and is useless: a 1.5 Mt line out-consumes a 20 kt line every single day while
sitting nowhere near its own limit, so the answer would never change. The ratio
is scale-free. Exhausted quotas are excluded — they score highest by
construction, they have their own tile, and the question is which quota is
*about to* close.

> **Bands are computed on the value as displayed**, to one decimal — not on the
> raw one. Found on real data: order 058627 sat at 99.99% (2.15 t left of
> 17,093), so it printed "100.0%" while being banded critical. That put a row
> reading 100.0% under a tile labelled "75-99% used", and made the
> fastest-burning callout name a quota showing 100.0% in the same sentence as
> "exhausted quotas are excluded". The rule is that a band must agree with the
> number printed beside it.

The grade search is the one genuinely new capability: TrueNorth maps engineering
grades to quota categories, which is domain knowledge held by a person, not
anything derivable from TARIC. Worth having only if researchers think in grades
rather than category numbers.

The import-history charts are probably part of what he meant by *"some of the
information there is redundant"*, but that is worth confirming rather than
guessing — trade-flow ingestion is a project, not a feature.

## Possible next steps, not started

- **Source-side "last allocation date."** TARIC publishes it and the scraper
  already reads it, but it is not persisted to the history CSV. It would answer
  "is this quota dormant or actively drawing?" better than the scrape timestamp.
  Adding it means one new history column, which older rows would carry blank.
- **Cross-quarter comparison view.** The data model supports it today
  (`day_in_quarter` exists precisely for this); no UI is built because there is
  only one quarter of history so far. Worth building around October 2026, when
  Q2 gives it something to compare against.
- **CSV/Excel export** from a filtered view, if researchers start copying out of
  the table.
