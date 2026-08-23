# -*- coding: utf-8 -*-
"""
Build script for the MEPS Quota Data Downloader EXE.

Output: dist/MEPS_Quota_Downloader.exe, a single-file console exe.

NOT STDLIB-ONLY ANY MORE, and that was a deliberate trade. download.py's own
imports are still standard library, but it can now render the dashboard locally
from the CSV it downloads, and that path imports webapp (Jinja2 + SQLAlchemy).
The templates are bundled as data so the exe can render without the repository.

Measured cost: 7.49 MB -> 14.16 MB, +6.67 MB, 1.89x. Accepted because it is
still one small file to hand someone, and because it makes the downloader
self-sufficient when the prebuilt bundle is missing or the release is
unreachable. Flask is excluded on purpose -- the renderer builds its Jinja
environment directly (webapp/render.py), so no web framework is bundled.

The reasoning is recorded in docs/INTERNAL_SITE.md.

Usage:
    python build/build_downloader_exe.py
"""
import os
import shutil
import stat
import subprocess
import sys

BUILD_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BUILD_SCRIPT_DIR)
DIST_FOLDER = os.path.join(PROJECT_DIR, "dist")
PYINSTALLER_BUILD = os.path.join(BUILD_SCRIPT_DIR, "_dl_build_temp")

# Everything heavy stays out. Jinja2 and SQLAlchemy now come in deliberately
# (local rendering); flask and werkzeug do NOT -- webapp/render.py builds the
# Jinja environment directly so the exe carries no web framework.
EXCLUDE_MODULES = [
    "pandas", "numpy", "openpyxl", "bs4", "lxml", "requests", "selenium",
    "pytest", "scipy", "matplotlib", "PIL", "tkinter", "_tkinter",
    "IPython", "notebook", "jupyter", "pydantic",
    "flask", "werkzeug", "click", "itsdangerous", "blinker",
]


def _force_rmtree(path):
    def onerror(func, fpath, exc_info):
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)
    if os.path.exists(path):
        shutil.rmtree(path, onerror=onerror)


def main():
    entry = os.path.join(PROJECT_DIR, "download.py")
    if not os.path.exists(entry):
        print(f"ERROR: {entry} not found")
        return 1

    _force_rmtree(PYINSTALLER_BUILD)
    exe_path = os.path.join(DIST_FOLDER, "MEPS_Quota_Downloader.exe")
    if os.path.exists(exe_path):
        os.remove(exe_path)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "MEPS_Quota_Downloader",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath", DIST_FOLDER,
        "--workpath", PYINSTALLER_BUILD,
        "--specpath", BUILD_SCRIPT_DIR,
        # so `from webapp import ...` resolves during analysis
        "--paths", PROJECT_DIR,
        # the templates must travel with the exe: local rendering has no repo
        "--add-data", os.path.join(PROJECT_DIR, "webapp", "templates") + os.pathsep + os.path.join("webapp", "templates"),
        entry,
    ]
    for mod in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", mod])

    print("Building MEPS_Quota_Downloader.exe (onefile)...")
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print("Build FAILED")
        return 1

    _force_rmtree(PYINSTALLER_BUILD)
    spec = os.path.join(BUILD_SCRIPT_DIR, "MEPS_Quota_Downloader.spec")
    if os.path.exists(spec):
        os.remove(spec)

    size = os.path.getsize(exe_path)
    print(f"\nBUILD SUCCESSFUL: {exe_path} ({size:,} bytes)")
    print("Distribute this single file — colleagues double-click it to fetch")
    print("the latest data published by the daily GitHub Actions run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
