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
| **Built and tested** | ✅ 84 tests, running against the real 10,024-row history |
| **Deployed to the server** | ⏳ Not yet — blocked on SSH access (see below) |
| **Database** | SQLite today; SQL Server is a connection-string change |
| **Reachable by researchers** | ⏳ Needs a decision + a firewall change |

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
| Power BI / other consumers | no | **yes** |
| Backed up by the existing job | no | yes |

**Recommendation: start on SQLite, move to SQL Server when the Power BI or
shared-access case is real.** Moving is `--rebuild` against the new URL; no data
is lost because the CSV is canonical. Starting on SQL Server means asking
permission for something not yet needed.

### 2. How researchers reach it

This is the harder one, and it is genuinely blocked on infrastructure.

The server is **standalone in `WORKGROUP`, not on `meps.local`** — there is no
internal LAN path to it. Everyone, including researchers, reaches it over the
internet. So "internal" here means *authenticated and IP-restricted*, not
network-isolated. IIS already owns ports 80 and 443 with the live public API.

| Option | Work | Who is needed |
|---|---|---|
| **A. New IIS site on a new port**, reverse-proxying to the Flask app on `127.0.0.1` | new port opened in **both** firewalls | ⚠️ **IONOS account holder** for the upstream firewall, plus the box owner |
| **B. Host header on 443** under the existing IIS site | DNS record + certificate + editing a **production** site's config | box owner; touches the live API's IIS |
| **C. SSH tunnel** (`ssh -L 8081:127.0.0.1:8081 …`) | none | nobody — works today |

**C works right now and needs no permission**, but it is fine for one or two
technical users and unreasonable for a researcher who just wants a bookmark.

**A is the right destination.** It keeps the production site untouched and puts
the tracker on its own port. It needs the IONOS account holder, who is the same
person who had to open port 22 — so this is a known, previously-executed request.

Until then the app binds to `127.0.0.1` by default, deliberately: this host
already has SQL Server exposed to the open internet, and nothing here should
widen that surface by accident.

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
