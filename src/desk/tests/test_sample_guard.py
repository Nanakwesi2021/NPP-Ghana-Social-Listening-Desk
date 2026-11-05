"""Live collection commands refuse to run in sample mode (desk_site/safety.py), so real items and
trend calculations can never be written into the fictional Sample shift database again.
Offline: every network entry point is stubbed, and the tests check none is reached."""
import os
from datetime import datetime, timezone
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from desk import trends
from desk.ingest import replay
from desk.models import Item, Platform, PollRun, Source, TrendCalculation, TrendRow

SAMPLE_AS_OF = datetime(2026, 11, 3, 10, 37, tzinfo=timezone.utc)
EMPTY_RSS = b"<rss version='2.0'><channel></channel></rss>"
EMPTY_ATOM = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'

# Every command that reads a live source, stores live trend data or sends to the war room.
LIVE_COMMANDS = [
    ("collect_news", {}),
    ("collect_social", {}),
    ("scan_networks", {}),
    ("run_worker", {"once": True}),
    ("recompute_trends", {}),
    ("brief_shift", {"telegram": True}),
]


def stored():
    return {
        "items": Item.objects.count(),
        "polls": PollRun.objects.count(),
        "sources": Source.objects.count(),
        "calculations": TrendCalculation.objects.count(),
    }


class OfflineMixin:
    """Stub the feeds and record any attempt to open a connection (X, YouTube, news, Telegram)."""

    def setUp(self):
        super().setUp()
        self.urlopen = self.enterContext(mock.patch("urllib.request.urlopen"))
        self.news_fetch = self.enterContext(mock.patch("desk.collectors.rss.http_fetch", return_value=EMPTY_RSS))
        self.youtube_fetch = self.enterContext(
            mock.patch("desk.collectors.youtube.http_fetch_youtube", return_value=EMPTY_ATOM))


@override_settings(DESK_SAMPLE_MODE=True)
class SampleModeRefusalTests(OfflineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)

    def test_each_live_command_refuses_before_touching_the_network_or_database(self):
        before = stored()
        # Credentials present, so only the guard stands between these commands and X or Telegram.
        env = {"X_BEARER_TOKEN": "test-only", "TELEGRAM_BOT_TOKEN": "test-only", "TELEGRAM_CHAT_ID": "test-only"}
        with mock.patch.dict(os.environ, env):
            for name, options in LIVE_COMMANDS:
                with self.subTest(command=name), self.assertRaises(CommandError) as caught:
                    call_command(name, stdout=StringIO(), **options)
                message = str(caught.exception)
                self.assertIn("sample mode is on", message)
                self.assertIn("DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0", message)
                self.assertIn("PostgreSQL", message)
                self.assertIn("replay_sample", message)
        self.urlopen.assert_not_called()
        self.news_fetch.assert_not_called()
        self.youtube_fetch.assert_not_called()
        self.assertEqual(stored(), before)
        self.assertEqual(trends.latest().as_of, SAMPLE_AS_OF)

    def test_the_message_names_the_command_as_it_was_run(self):
        with self.assertRaises(CommandError) as caught:
            call_command("brief_shift", telegram=True, stdout=StringIO())
        self.assertIn("manage.py brief_shift --telegram", str(caught.exception))

    def test_brief_on_screen_still_works_in_sample_mode(self):
        out = StringIO()
        call_command("brief_shift", stdout=out)
        self.assertIn("#1 Electricity tariff increase", out.getvalue())

    def test_replay_sample_still_works_in_sample_mode(self):
        out = StringIO()
        call_command("replay_sample", stdout=out)
        self.assertIn("Sample shift as of 10:37 GMT", out.getvalue())
        row = trends.latest().rows.get(topic__slug="electricity-tariff")
        self.assertEqual((row.previous_count, row.current_count, row.change), (4, 12, 8))
        self.urlopen.assert_not_called()


@override_settings(DESK_SAMPLE_MODE=False)
class LiveDeskCommandTests(OfflineMixin, TestCase):
    """With sample mode off (the live desk), the same commands run as before."""

    def setUp(self):
        super().setUp()
        # No X token and no Telegram chat: X stays awaiting and alerts are skipped, all offline.
        self.enterContext(mock.patch.dict(os.environ, {"X_BEARER_TOKEN": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}))

    def test_each_live_command_runs(self):
        for name, options in LIVE_COMMANDS:
            with self.subTest(command=name):
                call_command(name, stdout=StringIO(), **options)
        self.assertTrue(self.news_fetch.called)
        self.assertTrue(self.youtube_fetch.called)
        self.urlopen.assert_not_called()

    def test_collection_and_trends_are_stored(self):
        call_command("run_worker", once=True, stdout=StringIO())
        self.assertTrue(PollRun.objects.filter(source__platform=Platform.NEWS).exists())
        self.assertTrue(PollRun.objects.filter(source__platform=Platform.YOUTUBE).exists())
        self.assertEqual(TrendCalculation.objects.count(), 1)

    def test_recompute_trends_for_a_given_time(self):
        out = StringIO()
        call_command("recompute_trends", as_of="2026-11-03T10:00:00Z", stdout=out)
        self.assertIn("Windows ending 10:00 GMT", out.getvalue())
        self.assertFalse(TrendRow.objects.filter(rank__isnull=False).exists())  # no items on a fresh live desk
