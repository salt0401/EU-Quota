# -*- coding: utf-8 -*-
"""
Tests for download.py - the colleague-facing data downloader
(standard library only; network is mocked)
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import download


class TestConfig:

    def test_points_at_public_raw_urls(self):
        assert download.BASE_URL.startswith('https://raw.githubusercontent.com/')
        assert 'salt0401/EU-Quota' in download.BASE_URL
        assert '/data/published' in download.BASE_URL

    def test_workbooks_come_from_release_assets(self):
        # xlsx files live on the rolling release (git stays small);
        # text files come from raw (committed = auditable history)
        assert download.FILE_SOURCES['MEPS_Quota_Update_latest.xlsx'] == download.RELEASE_BASE
        assert download.FILE_SOURCES['Quota_History.xlsx'] == download.RELEASE_BASE
        assert download.FILE_SOURCES['quota_history.csv'] == download.BASE_URL
        assert download.RELEASE_BASE.endswith('/releases/download/latest-data')

    def test_expected_file_set(self):
        assert 'MEPS_Quota_Update_latest.xlsx' in download.DATA_FILES
        assert 'quota_history.csv' in download.DATA_FILES
        assert 'Quota_History.xlsx' in download.DATA_FILES
        for name in download.DATA_FILES:
            assert name in download.FILE_SOURCES

    def test_stdlib_only(self):
        # the frozen exe must stay tiny: no third-party imports allowed
        import ast
        src_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'download.py')
        with open(src_path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        forbidden = {'pandas', 'numpy', 'openpyxl', 'requests', 'bs4', 'lxml', 'src'}
        assert not (imported & forbidden), f'non-stdlib imports: {imported & forbidden}'


class TestSelfUpdate:
    """Version check + rename-swap. A running exe cannot be overwritten on
    Windows but can be renamed — the update must use that, and must never
    raise (a failed check cannot block the data download)."""

    def _freeze(self, monkeypatch, tmp_path, current='2.8.0'):
        exe = tmp_path / 'MEPS_Quota_Downloader.exe'
        exe.write_bytes(b'OLD-EXE-CONTENTS')
        monkeypatch.setattr(download.sys, 'frozen', True, raising=False)
        monkeypatch.setattr(download.sys, 'executable', str(exe))
        monkeypatch.setattr(download, '__version__', current)
        return exe

    def test_parse_version(self):
        assert download._parse_version('2.8.0') == (2, 8, 0)
        assert download._parse_version('2.10.0') > download._parse_version('2.9.9')

    def test_not_frozen_never_updates(self, monkeypatch):
        monkeypatch.setattr(download.sys, 'frozen', False, raising=False)
        monkeypatch.setattr(download, 'fetch',
                            lambda url: (_ for _ in ()).throw(AssertionError('no fetch')))
        assert download.self_update() is False

    def test_same_or_older_version_no_update(self, monkeypatch, tmp_path):
        exe = self._freeze(monkeypatch, tmp_path)
        monkeypatch.setattr(download, 'fetch', lambda url: b'2.8.0\n')
        assert download.self_update() is False
        assert exe.read_bytes() == b'OLD-EXE-CONTENTS'

    def test_newer_version_swaps_exe(self, monkeypatch, tmp_path):
        exe = self._freeze(monkeypatch, tmp_path, current='2.8.0')
        new_payload = b'NEW-EXE-CONTENTS' * 100_000  # > MIN_PLAUSIBLE_EXE_BYTES

        def fake_fetch(url):
            return b'2.9.0\n' if url.endswith('.txt') else new_payload

        monkeypatch.setattr(download, 'fetch', fake_fetch)
        assert download.self_update() is True
        assert exe.read_bytes() == new_payload            # new exe in place
        assert (tmp_path / 'MEPS_Quota_Downloader.exe.old').exists()  # old parked

    def test_old_leftover_cleaned_on_next_run(self, monkeypatch, tmp_path):
        exe = self._freeze(monkeypatch, tmp_path)
        leftover = tmp_path / 'MEPS_Quota_Downloader.exe.old'
        leftover.write_bytes(b'stale')
        monkeypatch.setattr(download, 'fetch', lambda url: b'2.8.0\n')
        download.self_update()
        assert not leftover.exists()

    def test_implausibly_small_download_rejected(self, monkeypatch, tmp_path):
        exe = self._freeze(monkeypatch, tmp_path)

        def fake_fetch(url):
            return b'9.9.9\n' if url.endswith('.txt') else b'error page'

        monkeypatch.setattr(download, 'fetch', fake_fetch)
        assert download.self_update() is False
        assert exe.read_bytes() == b'OLD-EXE-CONTENTS'    # untouched

    def test_network_failure_never_raises(self, monkeypatch, tmp_path):
        self._freeze(monkeypatch, tmp_path)

        def fake_fetch(url):
            raise download.urllib.error.URLError('offline')

        monkeypatch.setattr(download, 'fetch', fake_fetch)
        assert download.self_update() is False  # skipped, not crashed


class TestRun:

    def _patch_fetch(self, monkeypatch, metadata=None, fail_files=(),
                     csv_rows=2):
        meta = metadata or {
            'generated_utc': '2026-07-06T05:45:00Z',
            'data_date': '2026-07-06',
            'quota_period': '01-Jul-2026 to 30-Sep-2026',
            'eu_quotas': 283, 'uk_quotas': 75,
            'eu_failed': 0, 'uk_failed': 0,
            'history_rows': 2,
        }
        calls = []

        def fake_fetch(url):
            calls.append(url)
            name = url.rsplit('/', 1)[-1]
            if name in fail_files:
                raise download.urllib.error.URLError('boom')
            if name == download.METADATA_FILE:
                return json.dumps(meta).encode('utf-8')
            if name == 'quota_history.csv':
                return b'header\n' + b'row\n' * csv_rows
            return b'FAKEDATA-' + name.encode()

        monkeypatch.setattr(download, 'fetch', fake_fetch)
        monkeypatch.setattr(download.time, 'sleep', lambda s: None)
        return calls

    def test_downloads_all_files(self, monkeypatch, tmp_path):
        calls = self._patch_fetch(monkeypatch)
        code = download.run(dest=str(tmp_path))
        assert code == 0
        for name in download.DATA_FILES:
            assert (tmp_path / name).exists()
        assert calls[0].endswith('metadata.json')  # freshness check first

    def test_partial_failure_returns_nonzero(self, monkeypatch, tmp_path):
        self._patch_fetch(monkeypatch, fail_files={'quota_history.csv'})
        code = download.run(dest=str(tmp_path))
        assert code == 1
        assert (tmp_path / 'MEPS_Quota_Update_latest.xlsx').exists()
        assert not (tmp_path / 'quota_history.csv').exists()

    def test_unreachable_repo_returns_error(self, monkeypatch, tmp_path):
        def fake_fetch(url):
            raise download.urllib.error.URLError('offline')
        monkeypatch.setattr(download, 'fetch', fake_fetch)
        assert download.run(dest=str(tmp_path)) == 1

    def test_stale_data_warns(self, monkeypatch, tmp_path, capsys):
        self._patch_fetch(monkeypatch, metadata={
            'generated_utc': '2026-06-20T05:45:00Z',
            'data_date': '2026-06-20',
            'eu_quotas': 283, 'uk_quotas': 75,
            'eu_failed': 0, 'uk_failed': 0, 'history_rows': 2,
        })
        download.run(dest=str(tmp_path))
        assert 'WARNING' in capsys.readouterr().out

    def test_zero_region_warns(self, monkeypatch, tmp_path, capsys):
        # a UK-less publish must be visible to the colleague, not silent
        self._patch_fetch(monkeypatch, metadata={
            'generated_utc': '2026-07-06T05:45:00Z',
            'data_date': '2026-07-06',
            'eu_quotas': 283, 'uk_quotas': 0,
            'eu_failed': 0, 'uk_failed': 0, 'history_rows': 2,
        })
        download.run(dest=str(tmp_path))
        assert 'zero quotas for one region' in capsys.readouterr().out

    def test_csv_metadata_mismatch_flagged(self, monkeypatch, tmp_path, capsys):
        # CDN mixed-commit race: row count differs from metadata -> retried
        # once, then flagged with nonzero exit
        self._patch_fetch(monkeypatch, csv_rows=5)  # metadata says 2
        code = download.run(dest=str(tmp_path))
        out = capsys.readouterr().out
        assert 'does not match metadata' in out
        assert code == 1
