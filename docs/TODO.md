# EU Quota Scraper — open work

Only **open** items live here. Completed work is not a checklist — it is in
`CHANGELOG.md` and git history, and a page of ticked boxes buries the two or
three things that actually need doing.

Pruned 2026-08-08: former Priorities 1–4 (MEPS report formatting, UK support,
the deleted login-triggered scheduler) were entirely `[x]`, superseded, or
described files that no longer exist.

---

## 1. New-regime maintenance — RECURRING, the important one

The EU/UK quota systems changed on 1 July 2026 (EU: Regulation (EU) 2026/1384 +
Implementing Regulation (EU) 2026/1457; UK: steel trade measure under the
Taxation (Cross-Border Trade) Act 2018).

- [ ] **1 Oct 2026 — quarter turn.** Update the `Current Quarter` column in
      `data/input/quota_urls.xlsx` and `data/input/uk_quota_urls.xlsx` to
      `2026-10-01`, and the UK `Template Quota Limit` column to the Oct–Dec
      tonnages (`q2_oct_dec_t` in
      `data/reference/regime-2026-07/uk_quotas.csv`).
      **Repeat every quarter** — `q3_jan_mar_t` on 1 Jan, `q4_apr_jun_t` on
      1 Apr. Procedure in `docs/DAILY_UPDATE_RUNBOOK.md`.
- [ ] **Jan 2027 — EU regulation renewal.** IR (EU) 2026/1457 defines the EU
      quotas only for 1 Jul – 31 Dec 2026; a renewal act is expected around
      January 2027. Check the new IR and rebuild `data/input/quota_urls.xlsx`
      if order numbers or volumes change. No preparatory work — the 2026-07-07
      decision is to adapt when it is published.
      **Expected symptom if it lands unnoticed:** the daily run fails loudly
      with an "N/M quotas failed to scrape" publish refusal. It will not
      publish nonsense.
- [ ] Update `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py` **only** if HMRC
      changes order numbers. They are not expected to rotate quarterly under
      the new measure.

## 2. Internal tracker site — IN PROGRESS

The sequencing decision of 2026-08-08 puts this ahead of Power BI. Full detail
in `docs/INTERNAL_SITE.md`; current queue in `docs/SESSION_LOG.md`.

- [ ] **DNS record + certificate for `quota.mepsinternational.com`** — the box owner is
      arranging both. **This is now the only external blocker**; then
      `install-iis-reverse-proxy.ps1 -ConfigureSite`
- [ ] Keep `waitress` running across a reboot (scheduled task, `At startup`)
- [ ] **LAST STEP: set the site password** — `tools\set-site-password.ps1`.
      Deliberately deferred to the end by owner instruction. **The site is
      UNAUTHENTICATED until then**, so it must not be reachable from outside
- [ ] **Migrate to SQL Server** once researchers confirm the site is useful —
      deferred, **not cancelled**

> **Trap, if anyone builds a "view an earlier date" page:** `queries.freshness()`
> reports the LATEST snapshot, so a page rendered for an older date would carry a
> header describing a different day. Thread the date through `freshness()` as
> well. This project has already shipped one view that computed the wrong date.

## 2b. Display-vs-logic: one item left

The 2026-08-23 sweep found six judgement calls. All are now closed except the
last, which was never started.

- [ ] **Not swept: the workbook as Excel opens it.** The audit covered Python
      and the website. Excel's own cell formatting could round a value that a
      formula then compares -- the same class, one layer further out. Deferred
      by owner decision, not forgotten

## 3. The 90% work — the highest-value content still to build

90% triggers a different customs process, so this is the number with an
operational consequence. None of it is built:

- [ ] **Count of quotas at or above 90%** as a masthead tile, alongside the
      exhausted count
- [ ] **"Crossed 90% on `<date>`"** per quota — computable exactly from the
      daily history, and something the reference site cannot do at all
- [ ] **Filter for ≥90%**, more useful than `?pressure=1` filtering whole
      categories
- [ ] Any Power BI port must land the 90% boundary **identically**, truncation
      rule included — otherwise the two systems disagree about whether a customs
      process applies

### Sizing

**~15 users** (research + analysis teams). A single shared password is thin for
that many — no per-person revocation — but adequate for the evaluation.
**Power BI licensing is a non-issue** (2026-08-22): every staff member already
holds a licence through their Data Hub dashboard, so there is no per-seat cost
and no procurement step.

## 4. Prophet forecasting (`beta/`) — DEFERRED

Phase 1 (data loader) is done. Phase 2 became *technically* possible at 30
new-regime days (~2026-08-04; 33 days as of 2026-08-07) — `MIN_PROPHET_DAYS` in
the code. **Starting Phase 2 is an owner decision, not a date**, and more
history still makes it better.

- [ ] `preprocessor.py` — rolling features, seasonality flags, outlier detection
- [ ] `simple_models.py` — naive, moving average, linear trend baselines
- [ ] Phase 3: Prophet models, days-to-exhaustion, cross-validation

`beta/` is a separate top-level directory with zero imports from/to `src/`.
Changes there cannot break the pipeline.

> **Regime boundary — already enforced.** `REGIME_START` in
> `beta/forecasting/data_loader.py` filters to 1 July 2026 by default. The old
> safeguard (189 EU quotas) and the new regime (283, different order numbers and
> volumes) are different quota populations; a model must never train across the
> boundary. Use `load_history()` — `load_all_snapshots()` is legacy and its
> input folder is no longer written.

Refresh the history figures with:

```bash
venv\Scripts\python.exe -c "from beta.forecasting import load_history, get_snapshot_summary; print(get_snapshot_summary(load_history()))"
```

---

## Notes

- EU scraping ~1–2 min (283 quotas), UK ~30 s (75 quotas), ~3 min combined
- **Main pipeline focus:** correct data, correct format in
  `meps_customer_template.xlsx`
- **Forecasting:** experimental, completely independent of the main pipeline

*Last updated: 02-Sep-2026*
