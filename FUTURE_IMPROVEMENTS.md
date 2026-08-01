# Future Improvements & Open Questions

The tracked list of open questions and deferred work, with status and dated
decisions. (`STARTUP.md` is onboarding-only and deliberately does not carry
these; colleague-facing questions are flagged in `PROJECT_STATUS.html`;
the build narrative is in `docs/SESSION_LOG_2026-07.md`.)

**Automation health, 2026-08-01:** 27 consecutive unattended days
(2026-07-06 → 2026-08-01), 9,666 history rows, zero failed scrapes, no gaps.

**Host change, 2026-08-02:** the daily run moved from GitHub Actions to the MEPS
company server. See `docs/SERVER_DEPLOYMENT.md`. Nothing in the list below
changed as a result — the pipeline, data format and distribution channel are
identical — but items are now implemented and tested *on the server*, which is
the environment they will run in.

---

## 0. Company-server migration — DONE (2026-08-02)

The daily scrape now runs on `WIN-RE1UH50A07U` under Windows Task Scheduler at
06:40 local, publishing to the same repository and the same `latest-data`
release. Colleagues' downloaders were not touched and did not need to be.

- **Why:** the company server is a standing requirement for MEPS data projects.
  Worth recording that the obvious rationale is wrong — this repo is *public*,
  so its GitHub Actions minutes were unlimited and free. Nothing was being
  consumed. The move is about where MEPS work is hosted.
- **Deliberately kept on GitHub Actions:** `build-downloader.yml` (needs a
  Windows runner, fires only when `download.py` changes) and the new
  `data-freshness-watchdog.yml` (a heartbeat must not live on the machine it
  watches). `daily-quota-update.yml` is retained with its schedule disabled as
  the emergency fallback.
- **Deferred hardening, not blocking:** `run.py` has no `--date` argument, so
  `publish_data()` stamps rows with local `date.today()`. At the 06:40 slot
  local and UTC always agree, and `server-daily-task.ps1` refuses to publish if
  they ever do not — but threading an explicit UTC date through `main.py` would
  remove the ambiguity rather than guard against it.

---

## 1. UK Category-1 "authorised use" quotas — DECISION PENDING (colleague)

Whether the tracker should keep the three authorised-use quotas
(order numbers 058673/058674/058675, ~5x the ordinary Category 1 volume)
that sit outside Tables 3 & 4 of the DBT notice.

- **Status:** currently INCLUDED (three extra rows on the UK tab).
- **Where it's raised:** flagged for colleagues in `PROJECT_STATUS.html`
  ("One decision for Friday") — to be raised at the run-through.
- **If the answer is "strict Tables 3 & 4 only":** revert steps are in
  `DECISION_NEEDED_UK_authorised_use.txt` (repo root).

## 1b. PROJECT_STATUS.html has gone stale — REFRESH BEFORE RESENDING

The colleague-facing page still reads "Status as of 6 July 2026" and asks for
a decision "for Friday" (a Friday now several weeks past), and its figures
(26 quotas past 75%) are from the launch week. The mechanics it describes are
still correct; only the dates/stats/framing are out of date.

- **Action:** refresh the header date, the stat tiles, and the decision
  framing before sending the page to anyone again.
- Current figures can be pulled from `data/published/quota_history_2026.csv`.

## 2. Quarterly transition (1 Oct 2026, then every quarter) — RESOLVED, procedure only

Decision (2026-07-07): the daily snapshot/report is ephemeral — useful only
on its day. Nothing beyond the history files needs preserving across a
quarter turn; the per-year history files are the permanent record and now
capture the complete daily picture per quota (volumes, percentages,
awaiting allocation, quota window, status).

- **What remains is routine maintenance**, documented in
  `docs/DAILY_UPDATE_RUNBOOK.md` (update `Current Quarter` columns + UK
  `Template Quota Limit`); the pipeline self-heals against stale dates
  meanwhile.
- Related decision (2026-07-07): history is split **one file per calendar
  year** (`quota_history_<YEAR>.csv` / `Quota_History_<YEAR>.xlsx`) — this
  is a long-lived project and no single file should grow forever.
  Implemented in v2.9.0; new years appear automatically.

## 3. January 2027 EU regulation renewal — WAIT FOR POLICY

Implementing Regulation (EU) 2026/1457 applies 1 July – 31 December 2026.
A renewal act is expected around January 2027 and may change order numbers.

- **Decision (2026-07-07):** no preparatory work; adapt when the renewal is
  published. The reminder colleagues see lives in `PROJECT_STATUS.html`
  ("Good to know").
- **Expected symptom if it lands unnoticed:** the daily run fails loudly
  with a "N/M quotas failed to scrape" publish refusal (it will not publish
  nonsense). Rebuild `data/input/quota_urls.xlsx` from the new act — the
  extraction approach is documented by the scripts referenced in
  `data/0702NewData/` and the repo history.

## 4. Prophet forecasting (beta/) — DEFERRED UNTIL ENOUGH DATA

Decision (2026-07-07): no forecasting work until a few months of new-regime
history exist (roughly October–November 2026 at the earliest; the history
started 2026-07-06 and grows 358 rows/day).

- **When resumed:** re-point `beta/forecasting/data_loader.py` at
  `data/published/quota_history_<YEAR>.csv` (map date→ds,
  balance_remaining_t→y per region+order_number, filter
  scrape_status == 'ok'), and never train across the 1 July 2026 regime
  boundary. Details in `docs/TODO.md` Priority 5.
