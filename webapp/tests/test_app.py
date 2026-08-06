# -*- coding: utf-8 -*-
"""
Route-level tests for the tracker site.

These exist because the pace bug they cover was invisible to the query tests:
`queries` returned entirely correct data, and the view then described the wrong
date. Anything the *view* computes needs a view-level test.
"""
import io
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

pytest.importorskip("flask", reason="webapp extras not installed")
pytest.importorskip("sqlalchemy", reason="webapp extras not installed")

from webapp import etl                              # noqa: E402
from webapp.app import create_app                   # noqa: E402
from webapp.db import get_engine                    # noqa: E402
from webapp.tests.test_etl_and_queries import row, write_history   # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 2026-07-06 (day 6) to 2026-08-02 (day 33) of Q1, climbing to 65%.
    body = ""
    for day, d in enumerate(["2026-07-06", "2026-07-20", "2026-08-02"]):
        body += row(d, "EU", "099837", cat="Metallic Coated Sheets - 4.B",
                    country="Korea", limit="110699",
                    alloc=str(10000 * (day + 1)), pct=str(20.0 * (day + 1)),
                    bal=str(110699 - 10000 * (day + 1)))
    published = write_history(tmp_path, body)
    engine = get_engine(f"sqlite:///{tmp_path/'app.db'}")
    etl.load(engine, published_dir=published)
    monkeypatch.setenv("QUOTA_SITE_PASSWORD_FILE", str(tmp_path / "nope.txt"))
    app = create_app(db_url=f"sqlite:///{tmp_path/'app.db'}", require_auth=False)
    app.config.update(TESTING=True)
    return app.test_client()


class TestIndex:

    def test_renders_and_groups_by_category(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "Metallic Coated Sheets - 4.B" in body
        assert "099837" in body

    def test_filters_do_not_error_on_junk_input(self, client):
        # These arrive from a URL, so bad values must degrade, not 500.
        for qs in ("?region=XX", "?min_pct=abc", "?q=" + "z" * 300, "?region=uk&min_pct="):
            assert client.get("/" + qs).status_code == 200


class TestQuotaDetail:

    def test_renders_the_quota(self, client):
        r = client.get("/quota/EU/099837")
        assert r.status_code == 200
        assert "099837" in r.get_data(as_text=True)

    def test_unknown_quota_and_region_404(self, client):
        assert client.get("/quota/EU/000000").status_code == 404
        assert client.get("/quota/XX/099837").status_code == 404

    def test_pace_is_measured_at_the_latest_data_date_not_the_quarter_start(self, client):
        """Regression: the view described quarter_start, so every quota read as
        'day 1 of 92, 1.1% elapsed' and therefore always 'ahead of the
        calendar'. The data was right; the date passed to describe() was not."""
        body = client.get("/quota/EU/099837").get_data(as_text=True)
        assert "day 33 of 92" in body, "should describe 2026-08-02, the latest day"
        assert "day 1 of 92" not in body
        assert "35.9% elapsed" in body
        assert "1.1% elapsed" not in body

    def test_ahead_or_behind_verdict_uses_the_corrected_pace(self, client):
        # 60% used at 35.9% elapsed is genuinely ahead. With the bug this said
        # "ahead" for the right reason by accident; the test pins the number.
        body = client.get("/quota/EU/099837").get_data(as_text=True)
        assert "running <b>ahead</b>" in body

    def test_bad_period_key_falls_back_instead_of_erroring(self, client):
        assert client.get("/quota/EU/099837?period=garbage").status_code == 200
        assert client.get("/quota/EU/099837?period=2026/27-Q9").status_code == 200

    def test_series_is_embedded_for_the_chart(self, client):
        body = client.get("/quota/EU/099837").get_data(as_text=True)
        assert 'id="series-data"' in body
        assert "day_in_quarter" in body


class TestHealthAndAuth:

    def test_healthz_reports_the_data_date(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200 and r.get_json()["ok"] is True
        assert r.get_json()["data_date"] == "2026-08-02"

    def test_auth_challenges_when_a_password_is_configured(self, tmp_path):
        pw = tmp_path / "pw.txt"
        io.open(pw, "w", encoding="utf-8").write("s3cret")
        engine = get_engine(f"sqlite:///{tmp_path/'a.db'}")
        published = write_history(tmp_path, row("2026-07-06"))
        etl.load(engine, published_dir=published)
        os.environ["QUOTA_SITE_PASSWORD_FILE"] = str(pw)
        try:
            app = create_app(db_url=f"sqlite:///{tmp_path/'a.db'}")
            c = app.test_client()
            assert c.get("/").status_code == 401
            # healthz stays open so a monitor does not need the password
            assert c.get("/healthz").status_code == 200
            import base64
            ok = base64.b64encode(b"meps:s3cret").decode()
            assert c.get("/", headers={"Authorization": f"Basic {ok}"}).status_code == 200
            bad = base64.b64encode(b"meps:wrong").decode()
            assert c.get("/", headers={"Authorization": f"Basic {bad}"}).status_code == 401
        finally:
            os.environ.pop("QUOTA_SITE_PASSWORD_FILE", None)


class TestOverviewHeadlines:
    """The masthead additions taken from the reference site.

    Route-level because the last bug of this shape was invisible to the query
    tests: the numbers were right and the view described the wrong date.
    """

    def test_masthead_shows_days_left_and_category_count(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "days left in quarter" in body
        assert "categories" in body
        # 2026-08-02 is day 33 of 92.
        assert ">59<" in body

    def test_fastest_burning_callout_names_the_quota_and_its_pace(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "Burning fastest:" in body
        assert "099837" in body
        assert "1.67&times;" in body        # 60.0% used / 35.9% elapsed

    def test_pressure_filter_hides_categories_with_nothing_at_risk(self, client):
        """The only quota here sits at 60%, below the 75% band."""
        assert "Metallic Coated" in client.get("/").get_data(as_text=True)
        body = client.get("/?pressure=1").get_data(as_text=True)
        assert "No quotas match those filters." in body

    def test_sort_toggle_renders_both_orders_without_erroring(self, client):
        for qs in ("?sort=name", "?sort=pressure", "?sort=nonsense", "?sort="):
            assert client.get("/" + qs).status_code == 200

    def test_new_filters_survive_junk_input(self, client):
        for qs in ("?pressure=yes", "?pressure=1&sort=name&min_pct=abc",
                   "?pressure=" + "z" * 200):
            assert client.get("/" + qs).status_code == 200
