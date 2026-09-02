# -*- coding: utf-8 -*-
"""Every path and command a tracked document quotes must actually exist.

**Why this test exists.** On 2026-09-02 both `README.md` and `STARTUP.md` — the
two files a newcomer is told to read first — instructed the reader to run
`python build/build_exe.py`. That script had been moved to `docs/archive/` some
time earlier and the entry-point documents were never updated, so the very first
command a new person ran could only fail. Nothing caught it, because nothing
checked. The individual mistake was easy to fix; the absence of a check was the
real defect, and this is the check.

**What it enforces.** In every tracked `.md` file:

* a markdown link to a repo file resolves;
* a backticked token that looks like a repo path resolves;
* a shell command in a fenced block that runs a script runs a script that is
  there, and `python -m x.y` names an importable module.

**What it deliberately does not enforce.** Prose. This is a reference checker,
not a documentation linter: it says nothing about whether the surrounding
sentence is still true. That still needs a human.

**When it fails.** Fix the document, or — if the reference is intentional —
add it to `ALLOWED` *with a reason*. The reason is the point. An allowlist
without one becomes a place to silence the test, which is how the original
defect survived.
"""
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# Every entry needs a reason. Keep it short and keep it honest.
ALLOWED = {
    # ---- produced at run time, never committed -----------------------------
    "MEPS_Quota_Update_latest.xlsx": "release asset, generated daily",
    "MEPS_Quota_Update_YYYYMMDD.xlsx": "dated output, generated per run",
    "downloader_version.txt": "release asset, written by CI",
    "eu_quota_raw_YYYYMMDD.xlsx": "dated output, generated per run",
    "uk_quota_raw_YYYYMMDD.xlsx": "dated output, generated per run",
    "quota-site/index.html": "inside the generated offline bundle",
    "uk_measure.html": "working file for a one-off extraction, never committed",
    "uk_measure_text.txt": "working file for a one-off extraction, never committed",
    # ---- deliberately outside the repository -------------------------------
    "_notes\\incidents.md": "on the server, outside the working tree by design",
    "_notes\\rounding-audit-2026-08-23.md": "on the server, outside the working tree",
    "_secrets\\sql-server-recon-2026-08-22.md": "on the server, outside the working tree",
    # ---- named precisely BECAUSE they no longer exist -----------------------
    "build/build_exe.py": "named in README/STARTUP as removed; this is the case that prompted this test",
    "FUTURE_IMPROVEMENTS.md": "named in STARTUP as deleted, so a reader is not left looking",
    "docs/INSTRUCTIONS.md": "deleted 2026-09-02, named in the session log's record of the deletion",
    "PROJECT_STATUS.html": "deleted 2026-09-02, named in the session log's record of the deletion",
}

# CHANGELOG.md is exempt from the path check. It is a record of what happened,
# so it names files that existed at the time and legitimately do not now.
# Rewriting it to satisfy a linter would falsify the history it exists to keep.
EXEMPT_FILES = {"CHANGELOG.md"}

LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)\)")
BACKTICKED = re.compile(
    r"`([A-Za-z0-9_./\\-]+\.(?:md|py|ps1|cmd|html|txt|yml|yaml|xlsx|csv|json|bat"
    r"|png|jpg|jpeg|svg|gif))`")
FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)
# `python x/y.py`, `venv\Scripts\python.exe x/y.py`, `powershell -File x.ps1`
SCRIPT_CMD = re.compile(
    r"(?:^|\s)(?:python(?:\.exe)?|venv[\\/]Scripts[\\/]python\.exe|py)\s+"
    r"(?!-)([A-Za-z0-9_./\\-]+\.py)")
PS_CMD = re.compile(r"(?:-File\s+|(?:^|\s))([A-Za-z0-9_./\\-]*tools[\\/][A-Za-z0-9_.-]+\.ps1)")
MODULE_CMD = re.compile(
    r"(?:python(?:\.exe)?|venv[\\/]Scripts[\\/]python\.exe)\s+-m\s+([A-Za-z0-9_.]+)")


def _tracked_markdown():
    try:
        out = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True)
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        pytest.skip("git not available; nothing to enumerate")
    return [f for f in out.split() if f not in EXEMPT_FILES]


def _exists(rel):
    return os.path.exists(os.path.join(ROOT, rel.replace("\\", "/")))


def _report(bad, advice="Fix the document, or add it to ALLOWED WITH A REASON."):
    return "\n".join(
        "  %s\n      quotes: %s\n      which does not exist. %s" % (f, ref, advice)
        for f, ref in bad)


def test_markdown_links_resolve():
    """A link a reader can click must go somewhere."""
    bad = []
    for f in _tracked_markdown():
        base = os.path.dirname(f)
        for target in LINK.findall(open(os.path.join(ROOT, f), encoding="utf-8").read()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            rel = os.path.normpath(os.path.join(base, target)).replace("\\", "/")
            if rel not in ALLOWED and not _exists(rel):
                bad.append((f, target))
    assert not bad, "dangling markdown links:\n" + _report(bad)


def test_quoted_paths_resolve():
    """A backticked path is a claim about the repository; it must hold."""
    bad = []
    for f in _tracked_markdown():
        text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        for ref in set(BACKTICKED.findall(text)):
            if ref in ALLOWED:
                continue
            norm = ref.replace("\\", "/")
            if _exists(norm):
                continue
            # a bare filename may live anywhere in the tree
            if "/" not in norm and _find_by_name(norm):
                continue
            bad.append((f, ref))
    assert not bad, "documents naming files that do not exist:\n" + _report(bad)


def _find_by_name(name):
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "venv", "__pycache__", "node_modules", "dist", "build"}]
        if name in filenames:
            return True
    return False


def test_commands_in_docs_are_runnable():
    """The one that would have caught `python build/build_exe.py`.

    Every script a fenced block tells the reader to run must be present, and
    every `-m module` must import.

    **ALLOWED does not apply here, deliberately.** It exempts prose — a document
    may name `build/build_exe.py` in order to say it was removed. A *command*
    naming it is the original defect verbatim, so there is no exemption: if a
    fenced block tells the reader to run something, it must be runnable.
    """
    bad = []
    for f in _tracked_markdown():
        text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        for block in FENCE.findall(text):
            for script in set(SCRIPT_CMD.findall(block)) | set(PS_CMD.findall(block)):
                if _exists(script.replace("\\", "/")):
                    continue
                bad.append((f, script))
            for mod in set(MODULE_CMD.findall(block)):
                top = mod.split(".")[0]
                if top in {"pytest", "pip", "venv", "PyInstaller"}:
                    continue
                if not os.path.exists(os.path.join(ROOT, *mod.split("."))) and \
                   not os.path.exists(os.path.join(ROOT, *mod.split(".")[:-1],
                                                   mod.split(".")[-1] + ".py")):
                    bad.append((f, "python -m " + mod))
    assert not bad, "documents quoting commands that cannot run:\n" + _report(
        bad, "There is no exemption for commands: fix the document, or restore the script.")


def test_the_allowlist_is_justified():
    """Every exemption carries a reason, and no dead entries accumulate.

    Without this, the allowlist becomes the place the next stale reference goes
    to be silenced — which is precisely how the original defect survived.
    """
    unreasoned = [k for k, v in ALLOWED.items() if not v or len(v) < 10]
    assert not unreasoned, "allowlist entries with no real reason: %s" % unreasoned

    stale = [k for k in ALLOWED if _exists(k.replace("\\", "/"))]
    assert not stale, (
        "these are on the allowlist but now exist, so the exemption is dead "
        "and should be deleted: %s" % stale)

    # Self-pruning: an exemption for a reference nobody makes any more is just
    # clutter that hides what the allowlist is really covering.
    corpus = "".join(open(os.path.join(ROOT, f), encoding="utf-8").read()
                     for f in _tracked_markdown())
    unreferenced = [k for k in ALLOWED if k not in corpus
                    and k.replace("\\", "/") not in corpus]
    assert not unreferenced, (
        "no tracked document mentions these any more, so their exemptions are "
        "dead and should be deleted: %s" % unreferenced)
