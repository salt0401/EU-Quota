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
| **Startup mechanism** | ✅ **2026-08-23** — `tools\quota-site-task.ps1` written and tested. Deliberately **not registered**: it refuses while the site would run unauthenticated |
| **Reachable by researchers** | ⏳ Not yet — blocked on the DNS record and certificate, and on the site password |

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
> and `quota.mepsinternational.com` does not resolve. Any one of those changing without the
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

> **A replacement VPS is being provisioned** through MEPS's IT company.
> Migration will be needed eventually; it is not urgent and the box owner will
> give notice. This is why `tools\install-iis-reverse-proxy.ps1` is a
> re-runnable, idempotent script with pinned payload hashes rather than a list
> of commands someone types twice.

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
| The database itself | ⏳ **not created, and not requested.** Our account has sufficient rights to create it, so this is a permission question rather than a technical one; the standing rule is to ask first. See *Do we need to ask?* below |
| Login for the task account | ✅ **already exists** — `NT AUTHORITY\SYSTEM` has had a login on this instance since 2024-12-11. Only database-level permissions would be needed, not a new login |
| `QUOTA_DB_URL` → SQL Server | ⏳ one environment variable |
| `--rebuild` against it | ⏳ under a minute |

That is the whole migration. It stays one action whenever it is wanted.

### Do we need to ask? Yes — and the answer makes the request small

Read-only reconnaissance of the local instance on 2026-08-22 settled it. Nothing
was created, altered or restarted; every statement was a `SELECT`.

**The technical answer: nothing is blocked.** Our account has sufficient rights
to create the database, the login the daily task would use already exists, there
is ample free space, and `model` is SIMPLE — so a new database inherits SIMPLE
and there is no log-backup chain to maintain, which is exactly right for a
rebuildable projection.

**The governance answer: ask anyway.** The standing rule — *"Do not touch the
existing `MSSQLSERVER` instance. It backs a live public API. Ask before creating
anything on it"* — is a permission question, and being technically able to
proceed is precisely why it is worth honouring rather than a reason to skip it.

The useful consequence is that the request is small and specific: *may I create
one small database on the instance*, not *please build us a database and a
login*.

**Two constraints worth stating when asking.** The instance is Express Edition,
which caps the buffer pool at roughly 1.4 GB while the existing databases
already total about 1.1 GB of data files — our working set is small, so the
added pressure is marginal, but not zero, and the instance backs a live API.
And the Power BI gateway's service account has no login on the instance, so a
data source cannot pass through as itself: it needs a **dedicated read-only
login scoped to `db_datareader` on the new database and nothing else**. That
matches what the instance already does — read-only logins on other databases
already exist — so it asks for nothing novel.

> The full reconnaissance — instance version and edition, the rights actually
> held, the existing logins, the gateway's identity and what it serves, free
> space — is deliberately **not** in this public repository. It is on the server
> at `_secrets\sql-server-recon-2026-08-22.md`.

**This is part of what is being requested, not something to do unilaterally** —
see the *Asked, but NOT agreed* table in `SESSION_LOG.md`. We have sufficient
rights to create both the database and the login ourselves; the standing rule is
to ask first, and being able to proceed is exactly why the rule is worth
keeping.

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

## The display-vs-logic rule

**The defect class: a value is rounded for display, but logic runs on the raw
value, so what a person sees contradicts what the system decided.** This project
hit it twice — the 99.99% banding bug, then the "Exhausted only" filter — so the
whole system was swept on 2026-08-23 rather than waiting for a third to surface
in front of a researcher.

**The rule, decided 2026-09-02: one figure, truncated, and everything classifies
on it.**

`render.displayed_pct()` is the only place a percentage becomes a display
figure, and it **truncates** — `math.floor` to one decimal, via `Decimal` so
binary floats cannot bite. `fmt_pct` prints exactly what it returns, and every
band, filter and sort in `queries` compares it. The row also carries
`pct_display`, so the offline bundle's client filter compares a figure *Python*
computed rather than rounding for itself; JavaScript owns no classification
rule.

**Why truncation rather than rounding, which was the first fix.** Because
`displayed_pct(v) <= v` always holds, the displayed figure can never cross a
threshold the raw value has not crossed. So "shown at or above 90%" implies
"actually at or above 90%" — for that threshold, for the other three, and for
any threshold added later, with nobody re-auditing them. Rounding gave the
opposite guarantee exactly where it mattered: 89.96% displayed as 90.0% while
the authoritative figure was below 90, and **90 is not a colour — it is where
imports go through a different customs process**.

The accepted cost: a quota at 99.99% prints 99.9% and bands critical rather than
exhausted. It is not exhausted, so that is defensible, but it is a real change
in what the page says. On 2026-09-02 data, 110 of 358 rows print one tick lower
and exactly two change band.

> **For the planned "crossed 90% on `<date>`":** decide the rule before writing
> it. It must compare `pct_display`, or reuse `band`, exactly as everything else
> does. Comparing the raw value would put the crossing date one day out from the
> badge beside it on day one.

Every judgement call the 2026-08-23 audit left open was closed on 2026-09-02
except one — the workbook as Excel itself opens it, which is in `docs/TODO.md`.
The audit's working record is at `_notes\rounding-audit-2026-08-23.md` on the
server.

The console line printed after a scrape counts the same bands, through the same
`quota_display.band_for`, so an operator and a researcher cannot read different
answers about the same day.

---

## Offline copy, shipped with the downloader

Colleagues can read the dashboard with no server, no Python and no network:
`MEPS_Quota_Site.zip` is published to the same rolling `latest-data` release as
the workbooks, and `download.py` extracts it into the dated output folder
alongside them. Open `quota-site/index.html` in any browser.

Built by `webapp/export.py`; regenerated every morning by the daily task.

### Two delivery paths, one renderer

| Path | How it works | When it is used |
|---|---|---|
| **C -- prebuilt bundle** | the server renders daily, publishes `MEPS_Quota_Site.zip` to the release, the downloader extracts it | the default and the fast path |
| **A -- local rendering** | the downloader loads the CSV it just fetched into a temporary SQLite via `webapp/etl.py`, then calls `webapp/export.py` | fallback when the bundle is missing, stale or the release is unreachable; forced with `--render-local` |

They are **the same renderer invoked from two places**, not two implementations.
Path A loads the CSV with the exact loader the server uses and then calls the
exact exporter the server calls. A test asserts the two outputs are
**byte-identical** for the same data, README aside (it carries the page count).

`--no-site` skips the dashboard entirely if someone wants data files only.

### The cost of local rendering, measured

`download.py` was deliberately standard-library only, which is why the exe was a
small single file. **Local rendering ends that**, and the number was measured
before it shipped rather than estimated:

| | Size |
|---|---|
| Baseline, stdlib-only | 7,852,785 bytes = **7.49 MB** |
| With local rendering | 14,869,625 bytes = **14.18 MB** |
| Delta | **+6.69 MB, 1.89x** |

The weight is SQLAlchemy (~19 MB of source on disk, compressing to about
6.5 MB in the bundle); Jinja2 and MarkupSafe are about 0.2 MB together. **No
pandas, no numpy** -- the rendering chain is Jinja2 + SQLAlchemy + stdlib, so
the 60 MB outcome that would have made this a bad trade does not arise.

**Flask is excluded on purpose.** The exporter used to borrow the Flask app
purely for its Jinja environment; `webapp/render.py` now builds that environment
directly, so no web framework is bundled -- and the live site, the server export
and the downloader all share one set of display filters.

`download.py`'s own imports are still standard library: the webapp imports are
inside the rendering function, so `python download.py` still works where the
package is absent, and a test enforces that.

### Single source of truth, deliberately

The obvious way to build this -- a second renderer with its own queries and its
own copy of the templates -- drifts the moment either side is touched, and the
drift is silent. So the exporter renders the **same Jinja templates** through
the **same Jinja environment**, from the **same contexts** in `webapp/views.py`,
that the live site uses. It is a different output target, not a second
implementation.

That required one refactor, done rather than worked around: the templates no
longer call `url_for` directly. They call `link_index()` / `link_quota()`, which
the live app resolves through `url_for` and the exporter resolves to relative
file paths. Six call sites, one seam.

### The rule that must not drift

The live index filters server-side and re-renders; a `file://` page cannot. So
the static index renders **every** row and hides what does not match.

**The band is never recomputed in JavaScript.** It is emitted as `data-band`
from the value Python already computed on the figure *as displayed*, and the
client filter only ever compares strings. This is the bug this project already
fixed once, and 90% now has an operational consequence -- it triggers a
different customs process -- so the classification stays in exactly one place.

The numeric `min_pct` filter *does* compare a raw percentage, because that is
what the server does. The asymmetry is real and is preserved rather than tidied.

> ### Found while building this: the "Exhausted only" filter disagrees with the badge
>
> On the **live site**, a quota at 99.98% is banded `exhausted` and displays
> "100.0%" -- but the "Exhausted only" filter (`min_pct=100`, raw comparison)
> **excludes it**. Two quotas are in that state today.
>
> This is the same class of bug as the banding fix, in a place that fix did not
> reach. The static bundle **reproduces the live behaviour exactly**, because
> the instruction was equivalence and a one-sided "fix" would be precisely the
> drift this design exists to prevent. **Fixing it is a live-site decision**:
> make the filter compare `round(pct, 1) >= 100`, or drop `min_pct=100` in
> favour of filtering on the band.

### Failure isolation

A failure here cannot fail, block or delay the data publish:

- The task step runs **last**, after the data is scraped, gated, committed,
  pushed and already uploaded, and runs `-AllowFailure` -- a WARN, not a failed
  run, so the watchdog stays quiet.
- The bundle renders into a **temporary directory** and is moved into place only
  once every page has succeeded, so a partial bundle never exists.
- The zip is written to a `.part` file and renamed, so a half-written archive is
  never visible to the uploader.
- The upload is attempted **only if generation returned 0**, so a failed render
  leaves yesterday's bundle on the release -- stale, but whole.
- `download.py` treats the bundle as optional: any failure prints a reason and
  the data download still reports success.

### Cost

**3.2 seconds** for 359 pages (index + 358 quotas), producing a **2.1 MB** zip.
Negligible against a ~200 s scrape, and it runs after everything time-critical.
If it ever does need bounding, the cheapest lever is that `quota_context()`
recomputes `freshness()` per page; caching it would remove most of the work.

> **The release is public.** This makes MEPS's *presentation* of the data
> publicly downloadable. The underlying numbers are already public on the same
> release (the CSV and both workbooks), so the marginal exposure is the
> presentation, not the data. Owner decision, taken knowingly. The bundle is
> checked by tests for absolute URLs, external references and anything
> secret-shaped.

### Keeping it running across a reboot

`tools\quota-site-task.ps1` registers a Task Scheduler task that starts
`waitress` at boot on `127.0.0.1:8081`.

```bash
powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Register     # refuses without the password file
powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Verify
powershell -ExecutionPolicy Bypass -File tools\quota-site-task.ps1 -Unregister   # clean rollback
```

**Task Scheduler, not a service wrapper.** NSSM or WinSW would be new
third-party software on a production host, and this deployment's standing claim
is that it added none. Task Scheduler already runs the daily task, so there is
one mechanism to understand rather than two; it survives a reboot, restarts a
crashed process, and ports to the replacement VPS unchanged. The honest cost is
that Task Scheduler is not a service manager -- it cannot tell a wedged process
from a healthy one, which is why `-Verify` probes `/healthz` over HTTP instead
of trusting the task state.

**It runs as `SYSTEM`, matching the daily task.** Least privilege would prefer
`LOCAL SERVICE`, and that was considered and rejected *for now* with a concrete
reason: `LOCAL SERVICE` has no grant of any kind on the project tree, the
tracker database is owned by `Administrators` with only `ReadAndExecute` for
`Users` — and `create_all()` issues DDL, so the serving identity needs
**write** — and the password file is ACL'd `SYSTEM:R` + `Administrators:F`. So
`LOCAL SERVICE` would need three ACL changes on a live box, one of them to a
secrets file, for an app that binds loopback only and sits behind IIS. `SYSTEM`
needs none.

> **Deferred improvement, recorded rather than pretended away:** move the site
> to a dedicated low-privilege account. The cost is the three ACL grants above;
> the benefit is that a web-facing process stops running as `SYSTEM`. Worth
> doing when the site stops being an evaluation, and worth doing *on the
> replacement VPS* where the ACLs can be set up correctly from the start
> instead of retrofitted.

> ### The tool enforces the ordering, so nobody has to remember it
>
> **`-Register` and `-Serve` refuse outright unless the site password file
> exists.** Loopback-only binding means an unauthenticated instance is not
> reachable from outside today — but the IIS proxy site is one command away,
> and a defence that depends on two facts staying true is weaker than one that
> depends on one. `-TestRun -AllowUnauthenticated` exists for local smoke tests,
> refuses any non-loopback bind address, and tears itself down.

**Status 2026-08-23: written, tested, and deliberately NOT registered.** The
guard was confirmed to refuse (exit 2), the serve path was confirmed to work
(`/healthz` 200, `/` 195 KB) and then torn down; nothing is listening on 8081
and no task is registered.

The daily task refreshes the database automatically after each publish. Pass
`-SkipEtl` to `server-daily-task.ps1` to suppress that.

> **Still to do before researchers can reach it**, in order:
>
> 1. **DNS record + TLS certificate** for the host name — the box owner is
>    arranging both. The only item that depends on someone else.
> 2. **Create the proxy site**: `install-iis-reverse-proxy.ps1 -ConfigureSite`
>    (refuses until the certificate exists).
> 3. **Register the startup task**: `quota-site-task.ps1 -Register`
>    (refuses until the password file exists).
> 4. **Set the password**: `set-site-password.ps1` — deliberately LAST, by
>    owner instruction.
>
> Steps 3 and 4 are mutually ordered by the tool itself: the task will not
> register while the site would serve unauthenticated. So in practice the
> password is set, then the task registered, then the site started.

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

## 90% is an operational threshold, not a colour

From the research colleague, 2026-08-08: *"75% and 90% work for me. **The 90% is
the key indicator as it triggers a slightly different customs process.**"*

This changes what the number is **for**. 75% is advisory — a quota worth
watching. **90% is a state change in someone's actual job**: past it, imports
against that quota go through a different customs process. It is not one of
three colours in a legend, and anything that reproduces these figures — a Power
BI port especially — must land on the same side of that boundary, rounding rule
included, or the two systems disagree about whether a customs process applies.

The work this implies is in `docs/TODO.md`. Thresholds are confirmed at
75 / 90 / 100.

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
