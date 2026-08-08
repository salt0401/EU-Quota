# Future Improvements & Open Questions

The tracked list of open questions and deferred work, with status and dated
decisions. (`STARTUP.md` is onboarding-only and deliberately does not carry
these; colleague-facing questions are flagged in `PROJECT_STATUS.html`;
current session state is in `docs/SESSION_LOG.md`, which is overwritten each
handover — the narrative of how the project was built lives in git history.)

**Automation health, 2026-08-07:** 33 consecutive unattended days
(2026-07-06 → 2026-08-07), 11,814 history rows, zero failed scrapes, no gaps.
The first 27 came from GitHub Actions; every run from 2026-08-02 is from the
company server.

**Host change, 2026-08-02:** the daily run moved from GitHub Actions to the MEPS
company server. See `docs/SERVER_DEPLOYMENT.md`. Nothing in the list below
changed as a result — the pipeline, data format and distribution channel are
identical — but items are now implemented and tested *on the server*, which is
the environment they will run in.

---

## 0. Company-server migration — DONE (2026-08-02)

The daily scrape now runs on the MEPS company server under Windows Task
Scheduler at 06:40 local, publishing to the same repository and the same `latest-data`
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

## 1. UK Category-1 "authorised use" quotas — SETTLED BY PRACTICE (2026-08-08)

Whether the tracker should keep the three authorised-use quotas
(order numbers 058673/058674/058675, ~5x the ordinary Category 1 volume)
that sit outside Tables 3 & 4 of the DBT notice.

- **Status: INCLUDED, and treated as settled.** They have been in every daily
  run since 2026-07-06 — the 75 UK count depends on them — and no one has asked
  for their removal in the month since the question was raised. Recording it as
  decided rather than leaving it "pending" indefinitely; if the answer ever
  changes, the revert steps are in
  `docs/archive/DECISION_NEEDED_UK_authorised_use.txt`.
- **Worth keeping in mind:** they are most of the true UK hot-rolled headroom,
  so excluding them would make the UK picture misleading, not merely narrower.

## 1b. PROJECT_STATUS.html — REFRESHED 2026-08-02

Dates, statistics and mechanics are now current as of 2026-08-02. **The decision
framing was deliberately left untouched** (owner instruction): the UK
authorised-use question in §1 is still open, so the section reads exactly as it
did, "One decision for Friday" heading included.

What changed, and why the rewrite was not a patch:

- The old callout said *"26 quotas past 75%, hot-rolled coil from Türkiye
  oversubscribed 2.3×"*. That claim has **expired**, not merely aged — the
  oversubscription was an awaiting-allocation spike in the regime's first week,
  and those volumes have since been allocated (peak pressure today is 0.21×).
  Patching the number would have preserved a story that is no longer true.
- Measured replacement: on 2026-07-06 there were **26 exhausted / 30 past 75%**;
  on 2026-08-02 there are **61 exhausted / 85 past 75%** (58 of the 61 are EU).
  The exhausted count has more than doubled in four weeks — a stronger and more
  useful headline than the one it replaced, and only visible *because* of the
  daily history.
- Also corrected: 05:30 UTC on GitHub Actions → a MEPS server each morning;
  "about 90 seconds" → about three minutes (measured 171–202 s); the failure
  path now describes the off-server watchdog; a 2 August timeline entry records
  the move and states plainly that nothing changed for colleagues.
- The stale "Ready ahead of the 17 July deadline" badge is replaced by
  "28 days running, no gaps, no failed scrapes".

Regenerate the figures with:

```bash
python -c "from beta.forecasting import load_history, get_snapshot_summary; print(get_snapshot_summary(load_history()))"
```

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
  `data/reference/regime-2026-07/` and the repo history.

## 4. Prophet forecasting (beta/) — DEFERRED UNTIL ENOUGH DATA

Decision (2026-07-07): no forecasting work until enough new-regime history
exists (the history started 2026-07-06 and grows 358 rows/day).

**Reconciled 2026-08-02** — this section said "October–November 2026 at the
earliest" while `docs/TODO.md` set the bar at 30 days, which is ~2026-08-04.
They disagreed. The 30-day figure is `MIN_PROPHET_DAYS` in the code, so it
wins as the *technical* threshold; "a few months" was a judgement about wanting
more than the bare minimum before trusting a forecast. Both are now stated
plainly: **30 days is when Phase 2 becomes possible (~2026-08-04); more history
still makes it better.** Starting Phase 2 is an owner decision, not a date.

- **Data plumbing: DONE 2026-08-02.** `load_history()` reads
  `data/published/quota_history_<YEAR>.csv`, maps it onto the existing column
  names so every other function works unchanged, drops `scrape_status != 'ok'`
  rows, and filters to `REGIME_START` (1 July 2026) by default. Done ahead of
  the deferral because the old `load_all_snapshots()` pointed at
  `data/snapshots/`, which nothing writes since v2.10.0 — it was no longer a
  future improvement but a dead code path. 15 tests; verified against the real
  10,024-row history.
- **Still deferred:** Phase 2 preprocessing and baseline models. Details in
  `docs/TODO.md` Priority 5.
