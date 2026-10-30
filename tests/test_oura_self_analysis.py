import json
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import oura_self_analysis as app


class TestLocalOura(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)
        for name, value in [("APP_HOME", path), ("DB_PATH", path / "test.sqlite3")]:
            p = patch.object(app, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_collection_mapping(self):
        self.assertEqual(app.COLLECTIONS["daily_sleep"], "daily")
        self.assertEqual(app.COLLECTIONS["heartrate"], "heartrate")

    def test_oura_extapi_scopes_are_normalized(self):
        raw = "extapi:daily extapi:heartrate extapi:workout extapi:tag extapi:spo2"
        self.assertEqual(
            app.parse_granted_scopes(raw),
            {"daily", "heartrate", "workout", "tag", "spo2"},
        )

    def test_plain_and_mixed_scopes_remain_supported(self):
        self.assertEqual(app.parse_granted_scopes("daily extapi:heartrate"),
                         {"daily", "heartrate"})
        self.assertEqual(app.parse_granted_scopes("extapi:daily_extra"),
                         {"daily_extra"})
        self.assertEqual(app.parse_granted_scopes(""), set())
        self.assertIsNone(app.parse_granted_scopes(None))

    def test_sync_with_prefixed_daily_scope_fetches(self):
        from argparse import Namespace
        args = Namespace(days=30, start=None, end=None,
                         collections="daily_sleep,sleep,daily_readiness,daily_activity")
        token = {"scope": "extapi:daily extapi:heartrate"}
        with patch.object(app, "token_load", return_value=token), \
             patch.object(app, "fetch_pages", return_value=2) as fetch:
            app.sync(args)
        self.assertEqual(fetch.call_count, 4)

    def test_sync_with_only_unrelated_scopes_skips(self):
        from argparse import Namespace
        args = Namespace(days=30, start=None, end=None, collections="daily_sleep")
        with patch.object(app, "token_load",
                          return_value={"scope": "extapi:heartrate"}), \
             patch.object(app, "fetch_pages") as fetch:
            app.sync(args)
        fetch.assert_not_called()

    def test_empty_grants_do_not_bypass_scope_check(self):
        from argparse import Namespace
        args = Namespace(days=30, start=None, end=None, collections="daily_sleep")
        with patch.object(app, "token_load", return_value={"scope": ""}), \
             patch.object(app, "fetch_pages") as fetch:
            app.sync(args)
        fetch.assert_not_called()

    def test_missing_refresh_token_does_not_overwrite(self):
        with patch.object(app, "secret_write") as writer:
            with self.assertRaises(app.OuraError):
                app.token_save({"access_token": "example", "expires_in": 123})
            writer.assert_not_called()

    def test_rotating_refresh_token_saved_before_use(self):
        expired = {
            "access_token": "old", "refresh_token": "old_refresh",
            "expires_at": time.time() - 100, "scope": "daily",
        }
        received = {
            "access_token": "new", "refresh_token": "new_refresh",
            "expires_in": 3600, "token_type": "bearer",
        }
        secrets_written = {}
        with patch.object(app, "token_load", return_value=expired), \
             patch.object(app, "exchange", return_value=received) as exchange, \
             patch.object(app, "secret_write",
                          side_effect=lambda k, v: secrets_written.update({k: json.loads(v)})):
            access = app.authorized_access_token()
        self.assertEqual(access, "new")
        self.assertEqual(secrets_written["oauth_tokens"]["refresh_token"], "new_refresh")
        self.assertEqual(secrets_written["oauth_tokens"]["scope"], "daily")
        exchange.assert_called_once_with({
            "grant_type": "refresh_token", "refresh_token": "old_refresh",
        })

    def test_valid_token_no_refresh(self):
        active = {
            "access_token": "valid", "refresh_token": "unused",
            "expires_at": time.time() + 3600,
        }
        with patch.object(app, "token_load", return_value=active), \
             patch.object(app, "exchange") as exchange:
            self.assertEqual(app.authorized_access_token(), "valid")
            exchange.assert_not_called()

    def test_sqlite_idempotent_upsert(self):
        with app.open_database() as con:
            app.save_page(con, "daily_sleep", [{
                "id": "row1", "day": "2026-10-29", "score": 71,
            }])
            app.save_page(con, "daily_sleep", [{
                "id": "row1", "day": "2026-10-29", "score": 78,
            }])
            n = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            raw = con.execute("SELECT payload FROM records").fetchone()[0]
        self.assertEqual(n, 1)
        self.assertEqual(json.loads(raw)["score"], 78)
        self.assertEqual(app.DB_PATH.stat().st_mode & 0o777, 0o600)

    def test_heartrate_record_key(self):
        row = {"timestamp": "2026-10-29T12:00:00Z", "source": "sleep", "bpm": 56}
        self.assertEqual(app.record_identity("heartrate", row),
                         "2026-10-29T12:00:00Z:sleep")

    def test_pagination(self):
        api_pages = [
            {"data": [{"id": "one", "day": "2026-10-29", "score": 81}],
             "next_token": "cursor"},
            {"data": [{"id": "two", "day": "2026-10-30", "score": 88}],
             "next_token": None},
        ]
        with app.open_database() as con, \
             patch.object(app, "authorized_access_token", return_value="fake_token"), \
             patch.object(app, "request_json", side_effect=api_pages) as request:
            processed = app.fetch_pages(con, "daily_sleep",
                                        date(2026, 10, 29), date(2026, 10, 31))
            count = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        self.assertEqual(processed, 2)
        self.assertEqual(count, 2)
        self.assertEqual(request.call_count, 2)
        self.assertIn("next_token=cursor", request.call_args_list[1].args[0])

    def test_repeating_page_cursor_fails_safely(self):
        api_pages = [
            {"data": [{"id": "one"}], "next_token": "same"},
            {"data": [{"id": "two"}], "next_token": "same"},
        ]
        with app.open_database() as con, \
             patch.object(app, "authorized_access_token", return_value="fake_token"), \
             patch.object(app, "request_json", side_effect=api_pages):
            with self.assertRaises(app.OuraError):
                app.fetch_pages(con, "daily_sleep",
                                date(2026, 10, 29), date(2026, 10, 31))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
