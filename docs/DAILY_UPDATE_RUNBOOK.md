# Daily Quota Update — Runbook

The scheduled task **MEPS EU Quota Daily Update** on the MEPS company server
scrapes all EU + UK quotas every day at 06:40 local and publishes:

| What | Where | How colleagues get it |
|---|---|---|
| `quota_history_<YEAR>.csv` (one per calendar year), `metadata.json` | committed to `data/published/` | `MEPS_Quota_Downloader.exe` (raw URL) |
| `MEPS_Quota_Update_latest.xlsx`, `Quota_History_<YEAR>.xlsx` | rolling release **latest-data** | `MEPS_Quota_Downloader.exe` (release URL) |

A second workflow (`.github/workflows/build-downloader.yml`) publishes the
downloader itself — `MEPS_Quota_Downloader.exe` and `downloader_version.txt` —
to the same **latest-data** release whenever `download.py` changes; installed
copies self-update from it (see *Releasing a downloader change* below).

The repository must stay **public** — anonymous downloads depend on it.

> **This runbook covers PIPELINE failures** — the scrape itself, the publish
> gates, the input workbooks. For failures of the *machine* — the task not
> firing, the credential, the release upload, antivirus — read
> **[SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md)** instead. Its triage table
> tells you which of the two you are looking at.

## When the daily run fails

Nothing on the server reports its own failure, so the alarm comes from
`.github/workflows/data-freshness-watchdog.yml`, which runs on GitHub at 09:00
UTC and opens (or comments on) an issue titled **"Daily quota update has not
published today"** when the committed `metadata.json` is not current.
Colleagues' downloads keep serving the last successful day, so one failed day is
not urgent — but a widening history gap is.

1. Read the run log on the server:
   `C:\DataScienceProject\EUQuota\data\logs\server_<YYYYMMDD>.log`
   (45-day retention). The log records the metadata line for the run:
   `data_date`, EU/UK counts and how many failed.
2. Common causes:
   - **`Refusing to publish: N/M quotas failed`** — the source website is
     down or changed markup, or (in January) the EU implementing regulation
     was renewed with **new order numbers** → rebuild
     `data/input/quota_urls.xlsx` from the new regulation.
   - **`Refusing to publish: the dominant EU quota window ended ...`** —
     the `Current Quarter` column in `data/input/quota_urls.xlsx` is stale
     (see quarterly maintenance below).
   - **`ERROR: --publish requested but UK scraping produced no rows`** —
     `data/input/uk_quota_urls.xlsx` is missing/empty or its header moved.
3. To backfill a missed day: the failed run's output is still on the server
   under `data/output/<date>/` and `data/published/` (uncommitted); or simply
   let the next successful run continue the history — the gap stays visible in
   the CSV dates, which is honest and preferable to a fabricated row.
4. Manual run, on the server:
   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\DataScienceProject\EUQuota\tools\server-daily-task.ps1 -Push
   ```
   Drop `-Push` to reproduce the failure without publishing anything.
5. After fixing anything under `src/`, `tools/` or `data/input/`, push the fix
   **and pull it on the server** — the server holds its own clone and will
   otherwise keep running the old code.

## Scheduled-workflow auto-disable

GitHub disables cron schedules after ~60 days without repository activity.
This no longer affects the daily scrape (it is a Windows scheduled task now),
but it **does** affect the freshness watchdog — which is the thing that would
tell you the scrape had stopped.

In normal operation the server's own daily commit keeps the repository active,
so the watchdog stays enabled. The failure mode to know about is the compound
one: if the server stops publishing for ~60 days *and* nobody commits anything,
GitHub eventually disables the watchdog too, and the alarm goes quiet along with
the pipeline. Re-enable under Actions → *Data freshness watchdog* → Enable.

## Releasing a downloader change

The downloader (`download.py`) is built into `MEPS_Quota_Downloader.exe` by
`.github/workflows/build-downloader.yml`, not the daily data run. To ship a
change to colleagues:

1. Edit `download.py` and **bump `__version__`** (e.g. `2.8.1` → `2.8.2`).
2. Push to `main`. The build workflow runs the downloader tests, rebuilds the
   EXE, writes `downloader_version.txt` (= `download.__version__`), smoke-runs
   the EXE against live data, and uploads both to the **latest-data** release
   (`gh release upload --clobber`).
3. Installed EXEs self-update on their next run: each reads
   `downloader_version.txt`, and if it names a newer version downloads the new
   EXE and swaps itself in (taking effect the run after). The EXE is obtained
   once — no re-distribution.

Forgetting the `__version__` bump means the release ships a new EXE but
installed copies see an unchanged version and never update — so always bump it.

Note: when a release renames/removes data files an old EXE still expects
(e.g. the v2.9.0 per-year history rename), colleagues on the old EXE see
exactly ONE degraded run — a couple of 404 "FAILED" lines and exit code 1,
while the latest report still downloads and the EXE self-updates during that
same run. The next run is clean. No action needed.

## Quarterly maintenance (next: 1 October 2026)

1. `data/input/quota_urls.xlsx` — set every `Current Quarter` cell to the
   new quarter start (e.g. `2026-10-01`). Until this is done the workflow
   self-heals by overriding stale dates with the computed quarter start,
   and the publish gate blocks genuinely stale data — but update it anyway.
2. `data/input/uk_quota_urls.xlsx` — set `Current Quarter` and update
   `Template Quota Limit` to the new quarter's tonnages from
   `data/reference/regime-2026-07/uk_quotas.csv` (columns `q1_jul_sep_t` … `q4_apr_jun_t`).
3. Push; the next daily run picks the changes up.

### What the input workbooks must contain

The only place these columns are written down. The scraper reads them by header
name, so a renamed or moved column surfaces as a scrape failure, not a warning.

`data/input/quota_urls.xlsx` (EU, 283 rows):

| Column | Required | Description |
|---|---|---|
| Order Number | Yes | 6-digit quota order number, e.g. `099801` |
| Quota Category | Yes | Product category name |
| Country | Yes | Country of origin |
| Current Quarter | Yes | Quarter start date, `YYYY-MM-DD` |
| URL | Auto | Generated by formula |

`data/input/uk_quota_urls.xlsx` (UK, 75 rows) — same, plus one:

| Column | Required | Description |
|---|---|---|
| Country | Yes | Country **or allocation name**, e.g. `European Union`, `India`, `Residual` |
| Template Quota Limit | Yes | Current-quarter limit in tonnes. The UK source does not publish it, so allocation is computed from this |

### A UK order number returns "NO DATA"

Order numbers are not expected to rotate quarterly under the current measure, so
treat this as a real change rather than routine maintenance:

1. Check the number on the UK Integrated Online Tariff site by hand.
2. Consult the DBT notice *"UK's steel trade measure from 1 July 2026"*.
3. Update it in **both** `data/input/uk_quota_urls.xlsx` and
   `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py` — the list in the code is the
   one the scraper validates against.

## January 2027

Implementing Regulation (EU) 2026/1457 applies 1 July – 31 December 2026.
Expect a renewal act around January 2027 — order numbers may change, which
surfaces here as the *"N/M quotas failed"* publish refusal. Rebuild the EU
input workbook from the new act (the `data/reference/regime-2026-07/` extraction scripts
in the repo history show how the current one was built).
