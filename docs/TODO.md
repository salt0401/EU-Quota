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

- [x] Webapp extras installed on the server, database built (2026-08-08)
- [x] `waitress` installed and verified serving the real data
- [ ] **Set the site password** — `tools\set-site-password.ps1`. Must happen
      before the site is reachable from anything but loopback
- [ ] **IIS reverse proxy** — needs the box owner; see *What to ask the box
      owner for* in `docs/INTERNAL_SITE.md`. **This is the blocker**
- [ ] Keep `waitress` running across a reboot (scheduled task, `At startup`)
- [ ] **Migrate to SQL Server** once researchers confirm the site is useful —
      deferred, **not cancelled**

## 3. Questions out with the research colleague

Answers pending; each changes what gets built.

- [ ] **Search by steel grade** (EN3B, 304, S355) — needs a grade→category map
      that is not in the source data. Domain knowledge held by a person, and
      the one genuinely new capability the reference site has
- [ ] **Status thresholds** — the reference site uses 70/90, we use 75/90/100.
      Arbitrary either way, so match his mental model
- [ ] **Import-history charts** (12-month, YoY, 3-month weighted average) —
      HMRC/Eurostat trade data, a different source entirely. A project rather
      than a feature

## 4. Prophet forecasting (`beta/`) — DEFERRED

Phase 1 (data loader) is done. Phase 2 became *technically* possible at 30
new-regime days (~2026-08-04; 33 days as of 2026-08-07) — `MIN_PROPHET_DAYS` in
the code. **Starting Phase 2 is an owner decision, not a date**, and more
history still makes it better. Tracked in `FUTURE_IMPROVEMENTS.md` §4.

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

*Last updated: 08-Aug-2026*
