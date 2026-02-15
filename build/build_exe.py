# -*- coding: utf-8 -*-
"""
Build script for creating portable EXE package
Creates 'dist' folder with all necessary files for distribution

Usage:
    python build/build_exe.py

The script will:
1. Build EXE using PyInstaller
2. Copy necessary data files
3. Create distribution package in dist/ folder
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime

# Configuration - PROJECT_DIR is the parent of build/ folder
BUILD_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BUILD_SCRIPT_DIR)  # Go up one level to project root

# Output folders
DIST_FOLDER = os.path.join(PROJECT_DIR, "dist")  # Final distribution folder
DIST_SUBFOLDER = os.path.join(DIST_FOLDER, "EU_Quota_Scraper")  # Subfolder for zipping

# Temporary build folders (will be cleaned up)
PYINSTALLER_BUILD = os.path.join(BUILD_SCRIPT_DIR, "_build_temp")
PYINSTALLER_DIST = os.path.join(BUILD_SCRIPT_DIR, "_dist_temp")


def clean_previous_build():
    """Remove previous build artifacts"""
    print("Cleaning previous build artifacts...")
    for folder in [DIST_FOLDER, PYINSTALLER_BUILD, PYINSTALLER_DIST]:
        if os.path.exists(folder):
            print(f"  Removing: {folder}")
            shutil.rmtree(folder)

    # Remove spec file if exists
    spec_file = os.path.join(PROJECT_DIR, "EU_Quota_Scraper.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)


def run_pyinstaller():
    """Run PyInstaller to create EXE"""
    print("\nBuilding EXE with PyInstaller...")

    # Entry point is now run.py in project root
    entry_point = os.path.join(PROJECT_DIR, "run.py")

    if not os.path.exists(entry_point):
        print(f"ERROR: Entry point not found: {entry_point}")
        return False

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "EU_Quota_Scraper",
        "--onedir",  # Create folder with EXE and dependencies
        "--console",  # Show console window for progress
        "--clean",
        "--noconfirm",
        "--distpath", PYINSTALLER_DIST,
        "--workpath", PYINSTALLER_BUILD,
        "--specpath", BUILD_SCRIPT_DIR,
        # Add data files
        "--add-data", f"{os.path.join(PROJECT_DIR, 'src')};src",
        "--add-data", f"{os.path.join(PROJECT_DIR, 'templates')};templates",
        # Hidden imports that might be missed
        "--hidden-import", "openpyxl",
        "--hidden-import", "pandas",
        "--hidden-import", "requests",
        "--hidden-import", "bs4",
        "--hidden-import", "lxml",
        "--hidden-import", "urllib3",
        "--hidden-import", "certifi",
        "--hidden-import", "charset_normalizer",
        "--hidden-import", "idna",
        "--hidden-import", "soupsieve",
        # Main script
        entry_point
    ]

    print(f"  Working directory: {PROJECT_DIR}")
    print(f"  Entry point: {entry_point}")
    result = subprocess.run(cmd, cwd=PROJECT_DIR)

    if result.returncode != 0:
        print("ERROR: PyInstaller failed!")
        return False

    print("  PyInstaller completed successfully!")
    return True


def create_dist_folder():
    """Create distribution folder with all necessary files"""
    print("\nCreating distribution folder...")

    # Create main folder and subfolder
    os.makedirs(DIST_SUBFOLDER, exist_ok=True)

    # Source paths
    pyinstaller_output = os.path.join(PYINSTALLER_DIST, "EU_Quota_Scraper")

    if not os.path.exists(pyinstaller_output):
        print(f"ERROR: PyInstaller output not found at {pyinstaller_output}")
        return False

    # Copy EXE and dependencies to subfolder
    print("  Copying EXE and dependencies...")
    for item in os.listdir(pyinstaller_output):
        src = os.path.join(pyinstaller_output, item)
        dst = os.path.join(DIST_SUBFOLDER, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    # Copy data/input folder
    print("  Copying data/input folder...")
    input_src = os.path.join(PROJECT_DIR, "data", "input")
    input_dst = os.path.join(DIST_SUBFOLDER, "data", "input")
    if os.path.exists(input_src):
        os.makedirs(os.path.dirname(input_dst), exist_ok=True)
        shutil.copytree(input_src, input_dst, dirs_exist_ok=True)

    # Create empty output folder structure
    print("  Creating output folder structure...")
    output_folder = os.path.join(DIST_SUBFOLDER, "data", "output")
    os.makedirs(output_folder, exist_ok=True)

    # Copy templates folder (should already be included by PyInstaller, but ensure it's there)
    print("  Ensuring templates folder exists...")
    templates_src = os.path.join(PROJECT_DIR, "templates")
    templates_dst = os.path.join(DIST_SUBFOLDER, "templates")
    if os.path.exists(templates_src) and not os.path.exists(templates_dst):
        shutil.copytree(templates_src, templates_dst)

    # Create README for users
    readme_content = """
================================================================================
       EU Quota Scraper - 歐盟/英國鋼鐵配額抓取工具
================================================================================

使用方式：
1. 雙擊 EU_Quota_Scraper.exe 執行程式
2. 等待程式抓取最新配額資料（約需 1-3 分鐘）
3. 完成後，輸出檔案會在 data/output/<今日日期>/ 資料夾中

輸出檔案：
- MEPS_Quota_Update_YYYYMMDD.xlsx - 客戶報告格式

注意事項：
- 需要網路連線才能抓取資料
- 如果抓取失敗，請檢查網路連線後重試
- 輸入資料檔案在 data/input/ 資料夾中

================================================================================
"""
    readme_path = os.path.join(DIST_SUBFOLDER, "使用說明.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print("  Created 使用說明.txt")

    return True


def cleanup_build_artifacts():
    """Remove intermediate build artifacts but keep dist folder"""
    print("\nCleaning up build artifacts...")
    for folder in [PYINSTALLER_BUILD, PYINSTALLER_DIST]:
        if os.path.exists(folder):
            print(f"  Removing: {folder}")
            shutil.rmtree(folder)

    # Remove .spec file
    spec_file = os.path.join(BUILD_SCRIPT_DIR, "EU_Quota_Scraper.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"  Removed: {spec_file}")


def main():
    print("="*70)
    print("EU Quota Scraper - Build Script")
    print(f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print(f"\nProject directory: {PROJECT_DIR}")
    print(f"Distribution folder: {DIST_SUBFOLDER}")

    # Step 1: Clean previous build
    clean_previous_build()

    # Step 2: Run PyInstaller
    if not run_pyinstaller():
        print("\nBuild FAILED!")
        return 1

    # Step 3: Create dist folder
    if not create_dist_folder():
        print("\nBuild FAILED!")
        return 1

    # Step 4: Cleanup
    cleanup_build_artifacts()

    print("\n" + "="*70)
    print("BUILD SUCCESSFUL!")
    print("="*70)
    print(f"\nDistribution folder created at:")
    print(f"  {DIST_SUBFOLDER}")
    print("\nContents of EU_Quota_Scraper folder:")
    for item in os.listdir(DIST_SUBFOLDER):
        item_path = os.path.join(DIST_SUBFOLDER, item)
        if os.path.isdir(item_path):
            print(f"  [DIR]  {item}")
        else:
            size = os.path.getsize(item_path)
            print(f"  [FILE] {item} ({size:,} bytes)")

    print("\nTo distribute: Zip the 'EU_Quota_Scraper' folder inside dist/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
