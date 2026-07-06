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
