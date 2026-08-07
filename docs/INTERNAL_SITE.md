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
| **One-off setup done** | ⏳ Not yet — `pip install`, `--rebuild`, password file. **RDP is enough; SSH is not required** |
| **Database** | SQLite today; **moving to SQL Server** — decided 2026-08-07, see below |
| **Reachable by researchers** | Via **Power BI** once the report is built; the site routes below are superseded |

> **SSH being down does not block this.** `tools/server-daily-task.ps1` runs
> `git pull --rebase origin main` before pushing, so anything merged to `main`
> lands on the server at 05:43 the next morning with no action from anyone.
> Until the extras are installed the ETL step logs a `WARN` each morning and the
> publish carries on untouched — which is exactly what the non-fatal design is
> for.

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

### 1. Where the database lives

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

**Update 2026-08-07: SQL Server, at the instance owner's own request.** The
original recommendation below was SQLite-first, with a real Power BI need named
as the trigger for moving. That trigger has now fired — the colleague who runs
the instance asked for the dashboard in Power BI and offered a database, which
also settles the ask-first constraint, since he is the person to ask. See
`SESSION_LOG.md` for the migration steps.

The original reasoning, kept for the record:

The usual objections do not survive contact with this project:

- **Concurrency** — one writer (the 05:43 ETL), a few readers. In WAL mode
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

> **Host-specific caveat.** Defender and Acronis run with zero exclusions and can
> hold a handle on a file just after it is written. If the ETL ever fails with
> `WinError 32` on the database file, that is the cause — not the code — and
> re-running will succeed.

### 2. How researchers reach it

> **Superseded 2026-08-07:** researchers will reach the data through **Power
> BI** with their existing Microsoft accounts, so none of the routes below need
> building. Kept for the record.

The server is **standalone in `WORKGROUP`, not on `meps.local`** — there is no
internal LAN path to it. Everyone, including researchers, reaches it over the
internet. So "internal" here means *authenticated*, not network-isolated.

**These are two independent decisions**, and conflating them is what made this
look harder than it is:

#### (a) The network path

Port **443 is already open in both firewalls** (verified 2026-08-05). A route
that reuses it needs
**no firewall change at either layer**, which removes the IONOS account holder
from the picture permanently.

| Route | Cost | Who is needed |
|---|---|---|
| **New IIS site on 443**, own hostname via SNI, reverse-proxy to Flask on loopback | URL Rewrite + ARR install **restarts IIS — seconds of downtime on the live API** — plus a DNS record and a certificate | box owner, with notice |
| New port served directly by `waitress` | new port in **both** firewalls; TLS handled in Python | ⚠️ IONOS account holder, repeatedly |
| Path under the existing hostname (`/quota`) | no DNS or certificate, but edits the **production** site's config | box owner; highest blast radius |
| SSH tunnel | none | nobody — unusable for non-technical users |

**Take the first.** A one-time, schedulable IIS restart buys permanent
independence from the account holder, and adding a *new site* is far safer than
editing the live one. Confirm the modules install without a **reboot** first —
nothing requiring a reboot can go on this box.

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

A password makes the site useless to a passer-by; it is not a substitute for
restricting who can reach the port. Do both, or neither is worth much.
`/healthz` stays open so a monitor does not need the password.

---

## Running it

```bash
# one-off: install the extras into the venv (NOT in requirements-ci.txt)
venv\Scripts\python.exe -m pip install -r requirements-webapp.txt

# load the database from the published history
venv\Scripts\python.exe -m webapp.etl --rebuild

# serve
venv\Scripts\python.exe -m webapp.app                 # 127.0.0.1:8081
```

The daily task refreshes the database automatically after each publish. Pass
`-SkipEtl` to `server-daily-task.ps1` to suppress that.

For a real deployment, run it behind a WSGI server rather than Flask's
development server — `waitress` is the pragmatic Windows choice
(`waitress-serve --listen=127.0.0.1:8081 --call webapp.app:create_app`).

### Tests

```bash
python -m pytest webapp/tests -q          # expect 84 passed
```

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
| Bands at 70 / 90 | ⏳ **ask** — we use 75 / 90 / 100; arbitrary either way, so match his mental model |
| **Search by steel grade** (EN3B, 304, S355) | ⏳ **ask** — needs a grade→category map that is not in the source data |
| 12-month import history, YoY, 3-month weighted average | ⏳ **ask** — HMRC/Eurostat trade data, a different source entirely |

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
