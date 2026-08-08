# docs/archive/ — superseded material, kept deliberately

Files here are **no longer operational**. They are retained because they record
*why* something is the way it is, and that reasoning is not reconstructable from
the code.

Nothing here is maintained. If a statement in this folder contradicts a document
outside it, the document outside it wins.

Delete nothing from here to "tidy up" — git history already holds deleted files,
so anything placed here was judged worth finding *without* archaeology.

| File | What it was | Why it is here |
|---|---|---|
| `DECISION_NEEDED_UK_authorised_use.txt` | An open question raised 2026-07-06: should the UK Category 1 *authorised-use* quotas (`058673`/`058674`/`058675`) be tracked, given the brief scoped the UK to Tables 3 and 4? | **Resolved: yes, keep them.** They are in `data/input/uk_quota_urls.xlsx` and in `UK_QUOTA_ORDER_NUMBERS`, and the daily run confirms 75 UK quotas every morning. The file survives because it explains why those three rows exist and are ~5× the ordinary Category 1 volume — which nothing in the code says |
| `build_exe.py` | PyInstaller build of a portable EXE bundling the whole scraper, for running it by hand on a desktop | Superseded by the server deployment. Nobody runs the scraper by hand, and colleagues get data through `MEPS_Quota_Downloader.exe` instead. Nothing referenced it. Not to be confused with `build/build_downloader_exe.py`, which is **live** and used by `.github/workflows/build-downloader.yml` |

## Removed rather than archived

`data/0702NewData/message.txt` — the colleague's email of 2026-07-02 handing over
the new-regime quota details. Deleted from the working tree on 2026-08-08
because it named a person in a **public** repository, which the hygiene
convention in `SESSION_LOG.md` §7 forbids. Its factual content is preserved in
`data/reference/regime-2026-07/uk_quota_findings.md` and in the regime notes at
the top of `docs/ARCHITECTURE.md` and `docs/DATA_FLOW_ANALYSIS.md`. It remains in
git history; removing it from there would mean rewriting published history.
