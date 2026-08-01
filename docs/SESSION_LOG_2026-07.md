# Session Log — July 2026 rebuild & automation

Handoff record for the work done between **2 July and 1 August 2026**, written
so another machine (or another agent) can pick the project up with full
context. Setup instructions live in `STARTUP.md`; this file is the *why* and
*what happened*.

**State at the end of this session (2026-08-01): everything shipped, running
unattended, nothing in progress, working tree clean.**

---

## 1. What triggered the work

On 1 July 2026 both regimes the tracker followed were replaced:

- **EU** — the steel safeguard expired; Regulation (EU) 2026/1384 +
  Implementing Regulation (EU) 2026/1457 opened new quotas (new order numbers,
  50% out-of-quota duty, MFN + FTA parts, new quota types).
- **UK** — the safeguard was replaced by the DBT "steel trade measure"
  (new order numbers, volumes cut 51%, Ukraine exempt).

A colleague sent the EU regulation PDF plus a brief (`data/0702NewData/message.txt`)
asking for the update to be "ready and tested by 17 July". The UK announcement
was only *linked* in that message, and the link was lost.

## 2. What was delivered

### Regulation data extracted and verified
- All **283 EU quotas** from Annex I (`data/0702NewData/annex1_quotas.csv/xlsx`),
  with the official 30 category codes. Volumes reconcile **exactly** to the
  regulation's stated 18,345,922 t total — that reconciliation is what proves
  nothing was dropped or double-counted.
- **Annex II** country-eligibility sections 1–5 (`annex2_*.csv/json`) —
  including the "one country, multiple quotas" logic.
- The **UK announcement was tracked down independently** (the lost link):
  the DBT notice "UK's steel trade measure from 1 July 2026". Tables 3 & 4
  extracted (72 quotas, `058600`–`058671`) and cross-verified against the live
  HMRC API. Also discovered the **Category-1 authorised-use quotas**
  (`058673`–`058675`) that appear only on the online tariff — ~5× the ordinary
  Category 1 volume. See open item below.

### Pipeline migrated (and several live bugs fixed)
New input workbooks (283 EU / 75 UK); old ones archived under
`data/input/archive/`. Bugs found by validating against the *live* sites, not
just by reading code:

| Fix | Why it mattered |
|---|---|
| `awaiting_allocation` was silently zeroed (column-name mismatch) | Quotas showed as available when fully spoken for — 099801 was 2.3× oversubscribed on day 5 |
| Percentage `>1` heuristic removed | A 0.5%-allocated quota displayed as 50% |
| Validity dates parsed by regex (TARIC uses NBSP) | The report's period banner was blank |
| Failed/No-Data scrapes excluded from the customer report (EU **and** UK) | An outage looked like untouched quotas |
| Empty-shell TARIC pages count as failures | The Jan-2027 renewal would otherwise publish all-zero "exhausted" data |
| Customer template rewritten | Said 25% duty, 29 categories, wrong rollover rules |

### Re-architected: nobody runs the scraper
- **GitHub Actions** (`.github/workflows/daily-quota-update.yml`) scrapes daily
  at 05:30 UTC (free on a public repo) and publishes results.
- **Repository made public** — anonymous downloads depend on it. *Do not make
  it private.*
- **Colleagues run `MEPS_Quota_Downloader.exe`** (`download.py`, stdlib-only,
  single file) which fetches the published data. No login, no token.
- **The downloader self-updates**: it checks `downloader_version.txt` on the
  release and replaces itself when CI publishes a newer build
  (`build-downloader.yml` rebuilds on any `download.py` change). Distribution
  is one-time. **Bump `__version__` or installed copies never update.**
- **History split per calendar year** (`quota_history_<YEAR>.csv` in git,
  `Quota_History_<YEAR>.xlsx` on the release) — long-lived project, no file
  grows forever. Rows carry the full daily picture including awaiting
  allocation, quota window, and status.

### Hardened by adversarial review
Three review rounds (multi-agent, findings verified by refutation before
fixing) produced ~25 confirmed fixes. The recurring theme worth remembering:
**the dangerous failures are the ones that look like success** — a green
workflow publishing stale or empty data. Hence the publish *gates*: the run
refuses to publish mostly-failed scrapes, expired quota windows (stale
`Current Quarter`), or a UK-less dataset, and fails loudly instead.

## 3. Proven in production

- **27 consecutive days** of unattended daily runs (2026-07-06 → 2026-08-01):
  358 rows/day, **9,666 rows, zero failed scrapes, no missing dates**, no
  failure issues ever opened.
- The cron reliably fires **~2–3 h late** (07:15–08:57 UTC observed). That is
  normal GitHub shared-runner behaviour and harmless — data is stamped by date.
- The self-update path was verified end-to-end twice, including a real
  v2.8.0 → v2.8.1 propagation.

## 4. What the data already shows

Between 6 July and 18 July, EU quotas at ≥100% allocated grew **25 → 40**, and
those past 75% grew **28 → 61**. The FTA–CSQ overflow pools drain fastest.
Quota 099801 (Türkiye, hot-rolled 1.A) sat ~374 kt oversubscribed for most of
the quarter until TARIC cleared the pending queue around 18 July. None of this
was visible before the daily history existed.

## 5. Open items — pick up here

1. **UK authorised-use decision (needs the colleague, not code).** Whether to
   keep tracking `058673`–`058675`. Currently **included**. Flagged in
   `PROJECT_STATUS.html`; revert steps in `DECISION_NEEDED_UK_authorised_use.txt`.
2. **`PROJECT_STATUS.html` is stale** — it says "Status as of 6 July" and
   "One decision for Friday", which now reads oddly. Worth refreshing with
   current stats before sending it to anyone again.
3. **Quarter turn, 1 October 2026** — update the `Current Quarter` column in
   both input workbooks and the UK `Template Quota Limit`
   (from `data/0702NewData/uk_quotas.csv`). Procedure in
   `docs/DAILY_UPDATE_RUNBOOK.md`; the pipeline self-heals meanwhile.
4. **January 2027** — IR 2026/1457 expires 31 Dec 2026. A renewal may change
   order numbers; it will surface as a loud publish refusal, not bad data.
5. **Forecasting (`beta/`) — deferred** until a few months of history exist
   (~Oct–Nov 2026). When resumed, re-point the loader at
   `data/published/quota_history_<YEAR>.csv` and never train across the
   1 July 2026 regime boundary.

Full status of each: `FUTURE_IMPROVEMENTS.md`.

## 6. Notes for the next machine

- Setup, build, and verification steps: **`STARTUP.md`** (test baseline: 199).
- Always run Python with `PYTHONUTF8=1` — regulation text contains `Türkiye`,
  en-dashes, etc., and the default Windows console codepage crashes on them.
- The daily bot pushes to `main`, so **`git pull --rebase origin main` before
  pushing** or you will hit a rejected push.
- This project previously lived under a OneDrive path and was moved to
  `MEPS/02.Active/EU_Quota`. Only the current clone matters; nothing depends
  on the old location.
