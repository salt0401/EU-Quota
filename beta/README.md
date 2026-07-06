# beta/ — Experimental Features

This folder contains experimental features that are **completely independent**
of the main scraping/reporting pipeline (`src/`).

## Current: Forecasting Module (Phase 1)

Prophet time-series prediction for quota depletion.

### Status

- Phase 1 (data loader): **Done** — loads snapshots, prepares Prophet format
- Phase 2 (preprocessing + baselines): Pending
- Phase 3 (Prophet models): Pending
- Snapshots collected: 1/30+ new-regime days (need ~30 days for meaningful predictions; the counter restarted at the 1 July 2026 EU/UK regime change — pre-July snapshots are a different quota population and must not be mixed in)

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
