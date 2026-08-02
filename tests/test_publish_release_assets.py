# -*- coding: utf-8 -*-
"""
Tests for tools/publish_release_assets.py - the GitHub release uploader that
replaced `gh release upload --clobber` when the daily run moved to the company
server (network is mocked).
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import publish_release_assets as pra


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers if headers is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Records every call so the test can assert on ordering and semantics."""

    def __init__(self, release=None, missing=False, expiry_header=None):
        self.release = release or {"id": 42, "assets": []}
        self.missing = missing
        self.expiry_header = expiry_header
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if url.endswith("/rate_limit"):
            headers = ({pra.EXPIRY_HEADER: self.expiry_header}
                       if self.expiry_header else {})
            return FakeResponse(200, {}, headers=headers)
        if self.missing:
            return FakeResponse(404)
        return FakeResponse(200, self.release)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw.get("params", {}).get("name")))
        if "/releases" in url and "assets" not in url:
            return FakeResponse(201, {"id": 99, "assets": []})
        return FakeResponse(201, {"name": kw.get("params", {}).get("name")})

    def delete(self, url, **kw):
        self.calls.append(("DELETE", url))
        return FakeResponse(204)


@pytest.fixture
def publish_dir(tmp_path):
    d = tmp_path / "published"
    d.mkdir()
    for name in ("MEPS_Quota_Update_latest.xlsx",
                 "Quota_History_2026.xlsx",
                 "Quota_History_2027.xlsx"):
        (d / name).write_bytes(b"xlsx-bytes")
    return str(d)


class TestCollectAssets:

    def test_collects_report_and_year_workbooks(self, publish_dir):
        names = [os.path.basename(p) for p in pra.collect_assets(publish_dir)]
        assert names == ["MEPS_Quota_Update_latest.xlsx",
                         "Quota_History_2026.xlsx",
                         "Quota_History_2027.xlsx"]

    def test_ignores_stray_onedrive_conflict_copies(self, publish_dir):
        # src/publisher.py applies the same strict year-name rule to the
        # manifest; the release must not diverge from it.
        open(os.path.join(publish_dir, "Quota_History_2026 (1).xlsx"), "wb").close()
        open(os.path.join(publish_dir, "Quota_History_backup.xlsx"), "wb").close()
        names = [os.path.basename(p) for p in pra.collect_assets(publish_dir)]
        assert "Quota_History_2026 (1).xlsx" not in names
        assert "Quota_History_backup.xlsx" not in names
        assert len(names) == 3

    def test_raises_when_nothing_was_produced(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(RuntimeError, match="No workbooks found"):
            pra.collect_assets(str(empty))


class TestReadToken:

    def test_strips_surrounding_whitespace(self, tmp_path):
        f = tmp_path / "tok"
        f.write_text("  github_pat_abc123\n", encoding="utf-8")
        assert pra.read_token(str(f)) == "github_pat_abc123"

    def test_rejects_empty_file(self, tmp_path):
        f = tmp_path / "tok"
        f.write_text("\n\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="is empty"):
            pra.read_token(str(f))


class TestSession:

    def test_sends_bearer_token_and_api_version(self):
        s = pra.make_session("tok123")
        assert s.headers["Authorization"] == "Bearer tok123"
        assert s.headers["X-GitHub-Api-Version"] == "2022-11-28"


class TestPublishAssets:

    def test_dry_run_changes_nothing(self, publish_dir, monkeypatch):
        fake = FakeSession()
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        result = pra.publish_assets("o/r", "latest-data", "tok",
                                    pra.collect_assets(publish_dir), dry_run=True)
        assert result["uploaded"] == []
        assert all(c[0] == "GET" for c in fake.calls)

    def test_clobbers_existing_asset_before_upload(self, publish_dir, monkeypatch):
        fake = FakeSession(release={
            "id": 42,
            "assets": [{"name": "Quota_History_2026.xlsx", "id": 7}],
        })
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        pra.publish_assets("o/r", "latest-data", "tok",
                           pra.collect_assets(publish_dir))

        verbs = [c[0] for c in fake.calls]
        assert "DELETE" in verbs, "an existing asset must be removed first"
        # the delete must precede the re-upload of that same name
        delete_at = verbs.index("DELETE")
        upload_at = next(i for i, c in enumerate(fake.calls)
                         if c[0] == "POST" and len(c) > 2
                         and c[2] == "Quota_History_2026.xlsx")
        assert delete_at < upload_at

    def test_does_not_delete_assets_that_do_not_exist_yet(self, publish_dir, monkeypatch):
        fake = FakeSession(release={"id": 42, "assets": []})
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        result = pra.publish_assets("o/r", "latest-data", "tok",
                                    pra.collect_assets(publish_dir))
        assert [c[0] for c in fake.calls].count("DELETE") == 0
        assert len(result["uploaded"]) == 3

    def test_creates_the_release_when_missing(self, publish_dir, monkeypatch):
        fake = FakeSession(missing=True)
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        pra.publish_assets("o/r", "latest-data", "tok",
                           pra.collect_assets(publish_dir))
        creates = [c for c in fake.calls
                   if c[0] == "POST" and c[1].endswith("/releases")]
        assert len(creates) == 1

    def test_dry_run_does_not_create_a_missing_release(self, publish_dir, monkeypatch):
        fake = FakeSession(missing=True)
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        result = pra.publish_assets("o/r", "latest-data", "tok",
                                    pra.collect_assets(publish_dir), dry_run=True)
        assert result["dry_run"] is True
        assert all(c[0] == "GET" for c in fake.calls)


class TestUploadRetry:

    def test_raises_after_exhausting_retries(self, tmp_path, monkeypatch):
        import requests
        f = tmp_path / "a.xlsx"
        f.write_bytes(b"x")

        class AlwaysFails:
            def post(self, *a, **kw):
                raise requests.ConnectionError("connection reset")

        monkeypatch.setattr(pra.time, "sleep", lambda s: None)
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            pra.upload_asset(AlwaysFails(), "o/r", 1, str(f))

    def test_succeeds_on_a_later_attempt(self, tmp_path, monkeypatch):
        import requests
        f = tmp_path / "a.xlsx"
        f.write_bytes(b"x")

        class FlakyOnce:
            def __init__(self):
                self.n = 0

            def post(self, *a, **kw):
                self.n += 1
                if self.n == 1:
                    raise requests.ConnectionError("transient")
                return FakeResponse(201, {"name": "a.xlsx"})

        monkeypatch.setattr(pra.time, "sleep", lambda s: None)
        assert pra.upload_asset(FlakyOnce(), "o/r", 1, str(f))["name"] == "a.xlsx"


class TestTokenExpiry:
    """The push credential expires. Without this the first sign is a failed
    push the morning after; with it the daily log warns two weeks ahead."""

    def _future(self, days):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) + timedelta(days=days)
                ).strftime("%Y-%m-%d %H:%M:%S UTC")

    def test_parses_githubs_documented_format(self):
        dt = pra._parse_expiry("2027-08-02 00:00:00 UTC")
        assert dt is not None and dt.year == 2027 and dt.month == 8

    def test_parses_iso_variants(self):
        assert pra._parse_expiry("2027-08-02T00:00:00Z") is not None
        assert pra._parse_expiry("2027-08-02T00:00:00+00:00") is not None

    def test_unparseable_value_returns_none_rather_than_raising(self):
        assert pra._parse_expiry("next Thursday") is None
        assert pra._parse_expiry("") is None
        assert pra._parse_expiry(None) is None

    def test_warns_when_expiry_is_near(self, capsys):
        days = pra.check_token_expiry(FakeSession(expiry_header=self._future(5)))
        out = capsys.readouterr().out
        assert days is not None and days <= 14
        assert "WARNING" in out and "set-github-token" in out

    def test_quiet_when_expiry_is_far(self, capsys):
        days = pra.check_token_expiry(FakeSession(expiry_header=self._future(200)))
        out = capsys.readouterr().out
        assert days > 14
        assert "WARNING" not in out

    def test_reports_an_already_expired_token(self, capsys):
        pra.check_token_expiry(FakeSession(expiry_header=self._future(-3)))
        assert "EXPIRED" in capsys.readouterr().out

    def test_missing_header_is_reported_not_warned(self, capsys):
        # A classic PAT, or 'no expiration' on a fine-grained one. That is a
        # security observation, not a failure.
        assert pra.check_token_expiry(FakeSession()) is None
        out = capsys.readouterr().out
        assert "does not expire" in out and "WARNING" not in out

    def test_never_raises_when_the_check_itself_fails(self, capsys):
        # A token that still works today must publish today's data even if the
        # expiry lookup cannot answer.
        class Broken:
            def get(self, *a, **kw):
                raise RuntimeError("network down")

        assert pra.check_token_expiry(Broken()) is None
        assert "could not be checked" in capsys.readouterr().out

    def test_publish_checks_expiry_before_touching_the_release(self, publish_dir, monkeypatch):
        fake = FakeSession(expiry_header=self._future(3))
        monkeypatch.setattr(pra, "make_session", lambda token: fake)
        pra.publish_assets("o/r", "latest-data", "tok",
                           pra.collect_assets(publish_dir), dry_run=True)
        assert fake.calls[0][1].endswith("/rate_limit")


class TestTokenHandling:

    def test_token_is_never_a_command_line_argument(self):
        # A token passed as an argument is visible in the process list to every
        # account on this shared machine. Only --token-file is accepted.
        parser_src = io.open(pra.__file__, encoding="utf-8").read()
        assert '"--token-file"' in parser_src
        assert '"--token"' not in parser_src
