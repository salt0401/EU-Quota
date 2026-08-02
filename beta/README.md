# beta/ — Experimental Features

This folder contains experimental features that are **completely independent**
of the main scraping/reporting pipeline (`src/`).

## Current: Forecasting Module (Phase 1)

Prophet time-series prediction for quota depletion.

### Status

- Phase 1 (data loader): **Done** — `load_history()` reads the published daily history and prepares Prophet format
- Phase 2 (preprocessing + baselines): Pending
- Phase 3 (Prophet models): Pending
- History collected: **28/30 new-regime days** as of 2026-08-02 (~2026-08-04 for the 30-day threshold). The counter restarted at the 1 July 2026 EU/UK regime change — pre-July rows are a different quota population and are excluded automatically by `REGIME_START`
- **Data source:** `data/published/quota_history_<YEAR>.csv` (one file per calendar year), appended daily by the unattended run on the MEPS company server (358 rows/day). Use **`load_history()`**; `load_all_snapshots()` is legacy and nothing writes those files any more
- **Status:** Phase 2 is DEFERRED. It becomes technically possible at 30 days (~2026-08-04); starting it is an owner decision, not a date - see `FUTURE_IMPROVEMENTS.md` section 4

### Usage

```python
from beta.forecasting import load_all_snapshots, get_snapshot_summary

data = load_all_snapshots()
print(get_snapshot_summary(data))
```

### Dependencies

```bash
# Phase 1 works with just pandas (already installed)
# Phase 2+ will need:
pip install -r beta/requirements.txt
```

### Tests

```bash
pytest beta/tests/ -v
```

### Important

- This folder has **zero dependency** on `src/`
- Nothing in `src/` imports from `beta/`
- Changes here cannot break the main pipeline
