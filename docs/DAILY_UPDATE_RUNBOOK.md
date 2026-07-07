# Daily Quota Update — Runbook

The workflow `.github/workflows/daily-quota-update.yml` scrapes all EU + UK
quotas every day at 05:30 UTC and publishes:

| What | Where | How colleagues get it |
|---|---|---|
| `quota_history.csv`, `metadata.json` | committed to `data/published/` | `MEPS_Quota_Downloader.exe` (raw URL) |
| `MEPS_Quota_Update_latest.xlsx`, `Quota_History.xlsx` | rolling release **latest-data** | `MEPS_Quota_Downloader.exe` (release URL) |

A second workflow (`.github/workflows/build-downloader.yml`) publishes the
downloader itself — `MEPS_Quota_Downloader.exe` and `downloader_version.txt` —
to the same **latest-data** release whenever `download.py` changes; installed
copies self-update from it (see *Releasing a downloader change* below).

The repository must stay **public** — anonymous downloads depend on it.

## When the daily run fails

A failed run automatically opens (or comments on) a GitHub issue titled
**"Daily quota update failing"** and uploads whatever it produced as a
14-day artifact. Colleagues' downloads keep serving the last successful
day, so one failed day is not urgent — but a widening history gap is.

1. Open the run log: repository → Actions → Daily quota update.
2. Common causes:
   - **Pre-scrape tests failed** — a dependency release broke something;
     pin/adjust `requirements-ci.txt`, run the suite locally, push.
   - **`Refusing to publish: N/M quotas failed`** — the source website is
     down or changed markup, or (in January) the EU implementing regulation
     was renewed with **new order numbers** → rebuild
     `data/input/quota_urls.xlsx` from the new regulation.
   - **`Refusing to publish: the dominant EU quota window ended ...`** —
     the `Current Quarter` column in `data/input/quota_urls.xlsx` is stale
     (see quarterly maintenance below).
   - **`ERROR: --publish requested but UK scraping produced no rows`** —
     `data/input/uk_quota_urls.xlsx` is missing/empty or its header moved.
3. To backfill a missed day: a failed run's artifact contains its
   `data/published/`; or simply let the next successful run continue the
   history (the gap stays visible in the CSV dates).
4. Manual run: Actions → Daily quota update → **Run workflow**.

## Scheduled-workflow auto-disable

GitHub disables cron schedules after ~60 days without repository activity.
The daily bot commit normally keeps the clock fresh, but if the run fails
for weeks (no commits), the schedule can be disabled silently — the failure
issue is your alarm. Re-enable: Actions → Daily quota update → Enable.

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

## Quarterly maintenance (next: 1 October 2026)

1. `data/input/quota_urls.xlsx` — set every `Current Quarter` cell to the
   new quarter start (e.g. `2026-10-01`). Until this is done the workflow
   self-heals by overriding stale dates with the computed quarter start,
   and the publish gate blocks genuinely stale data — but update it anyway.
2. `data/input/uk_quota_urls.xlsx` — set `Current Quarter` and update
   `Template Quota Limit` to the new quarter's tonnages from
   `data/0702NewData/uk_quotas.csv` (columns `q1_jul_sep_t` … `q4_apr_jun_t`).
3. Push; the next daily run picks the changes up.

## January 2027

Implementing Regulation (EU) 2026/1457 applies 1 July – 31 December 2026.
Expect a renewal act around January 2027 — order numbers may change, which
surfaces here as the *"N/M quotas failed"* publish refusal. Rebuild the EU
input workbook from the new act (the `data/0702NewData/` extraction scripts
in the repo history show how the current one was built).
