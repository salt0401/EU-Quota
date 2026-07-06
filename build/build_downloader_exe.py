# -*- coding: utf-8 -*-
"""
Build script for the MEPS Quota Data Downloader EXE.

The downloader (download.py) is standard-library only, so this produces a
small SINGLE-FILE console exe — much easier to hand to colleagues than the
old scraper bundle. Output: dist/MEPS_Quota_Downloader.exe

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

# Everything heavy is excluded — the downloader must stay stdlib-only
EXCLUDE_MODULES = [
    "pandas", "numpy", "openpyxl", "bs4", "lxml", "requests", "selenium",
    "pytest", "scipy", "matplotlib", "PIL", "tkinter", "_tkinter",
    "IPython", "notebook", "jupyter", "pydantic",
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
