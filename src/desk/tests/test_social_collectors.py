import json
import os
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from desk.collectors import rss, x as x_collector, youtube as youtube_collector
from desk.coverage import partial_platforms
from desk.ingest import replay
from desk.models import Item, PollRun, Source, Topic

MOCK_X_RESPONSE = {
    "data": [
        {
            "id": "1855204000000000001",
            "text": "The dumsor situation in Kumasi is getting out of hand ECG needs to act now.",
            "author_id": "9901",
            "created_at": "2026-11-03T10:15:00.000Z",
            "lang": "en",
        },
        {
            "id": "1855204000000000002",
            "text": "NPP leadership briefing on economic measures today.",
            "author_id": "9902",
            "created_at": "2026-11-03T10:20:00.000Z",
            "lang": "en",
        },
    ],
    "includes": {
        "users": [
            {"id": "9901", "username": "accra_citizen"},
            {"id": "9902", "username": "ghana_daily"},
        ]
    },
    "meta": {
        "result_count": 2
    }
}

MOCK_X_CAPPED_RESPONSE = {
    "data": [
        {
            "id": "1855204000000000003",
            "text": "More discussion on electricity tariffs and PURC announcements.",
            "author_id": "9901",
            "created_at": "2026-11-03T10:25:00.000Z",
            "lang": "en",
        }
    ],
    "includes": {
        "users": [{"id": "9901", "username": "accra_citizen"}]
    },
    "meta": {
        "result_count": 1,
        "next_token": "b26v89c19zqg8o3frst4xyz998877"  # Signifies truncated / capped page
    }
}

MOCK_YOUTUBE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>JoyNews</title>
  <entry>
    <id>yt:video:abc123XYZ</id>
    <yt:videoId>abc123XYZ</yt:videoId>
    <title>Dumsor Crisis and Power Outages: Major Press Briefing</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123XYZ"/>
    <author><name>JoyNews</name></author>
    <published>2026-11-03T09:30:00+00:00</published>
    <summary>Live analysis of ECG power outages, load shedding and utility crisis.</summary>
  </entry>
</feed>"""


class SocialCollectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)
        rss.ensure_topics()
        cls.now = timezone.now()

    def test_x_collector_skips_when_no_token_in_env(self):
        source = x_collector.ensure_x_source()
        with patch.dict(os.environ, {"X_BEARER_TOKEN": ""}, clear=True):
            res = x_collector.collect_x(source, now=self.now)
            self.assertEqual(res.result, PollRun.Result.FAILED)
            self.assertIn("X_BEARER_TOKEN is not configured", res.note)

    def test_x_collector_complete_poll_ingests_and_tags(self):
        source = x_collector.ensure_x_source()
        source.kind = Source.Kind.COLLECTED
        source.save()

        def mock_fetch(url):
            return json.dumps(MOCK_X_RESPONSE).encode("utf-8"), "150"

        with patch.dict(os.environ, {"X_BEARER_TOKEN": "mock_token"}):
            res = x_collector.collect_x(source, fetch=mock_fetch, now=self.now)

        self.assertEqual(res.result, PollRun.Result.COMPLETE)
        self.assertEqual(res.new_items, 2)
        self.assertEqual(res.seen, 2)

        # Verify items stored
        item1 = Item.objects.get(external_id="x-1855204000000000001")
        self.assertEqual(item1.author, "@accra_citizen")
        self.assertEqual(item1.url, "https://x.com/accra_citizen/status/1855204000000000001")
        self.assertTrue(item1.topics.filter(slug__in=["dumsor", "dumsor-kumasi"]).exists())

        # Verify PollRun
        last_poll = source.polls.first()
        self.assertEqual(last_poll.result, PollRun.Result.COMPLETE)
        self.assertEqual(last_poll.new_items, 2)

    def test_x_collector_capped_poll_marks_platform_partial(self):
        source = x_collector.ensure_x_source()
        source.kind = Source.Kind.COLLECTED
        source.save()

        def mock_fetch(url):
            return json.dumps(MOCK_X_CAPPED_RESPONSE).encode("utf-8"), "0"

        with patch.dict(os.environ, {"X_BEARER_TOKEN": "mock_token"}):
            res = x_collector.collect_x(source, fetch=mock_fetch, now=self.now)

        self.assertEqual(res.result, PollRun.Result.CAPPED)
        self.assertIn("Capped", res.note)

        # Verify that Decision 005 detects X as a partial platform in trend windows
        start = self.now - timezone.timedelta(minutes=60)
        end = self.now + timezone.timedelta(minutes=5)
        partials = partial_platforms(start, end)
        self.assertIn("x", partials)

    def test_x_collector_http_429_marks_capped(self):
        source = x_collector.ensure_x_source()
        source.kind = Source.Kind.COLLECTED
        source.save()

        def mock_fetch_429(url):
            raise x_collector.XFetchError("Rate limit reached", status_code=429, is_rate_limit=True)

        with patch.dict(os.environ, {"X_BEARER_TOKEN": "mock_token"}):
            res = x_collector.collect_x(source, fetch=mock_fetch_429, now=self.now)

        self.assertEqual(res.result, PollRun.Result.CAPPED)
        self.assertIn("Rate limit", res.note)

    def test_youtube_collector_complete_poll_ingests_channel_feed(self):
        source = youtube_collector.ensure_youtube_source()

        def mock_fetch_yt(url):
            return MOCK_YOUTUBE_ATOM

        channels = [{"name": "JoyNews", "channel_id": "UC_J6Z06Cg4n9C26U2Q_aN8w"}]
        res = youtube_collector.collect_youtube(source, channels=channels, fetch=mock_fetch_yt, now=self.now)

        self.assertEqual(res.result, PollRun.Result.COMPLETE)
        self.assertEqual(res.new_items, 1)

        item = Item.objects.get(external_id="yt-abc123XYZ")
        self.assertEqual(item.author, "JoyNews")
        self.assertEqual(item.url, "https://www.youtube.com/watch?v=abc123XYZ")
        self.assertIn("Dumsor Crisis", item.title)
        self.assertTrue(item.topics.filter(slug="dumsor").exists())

    def test_youtube_collector_handles_feed_failure(self):
        source = youtube_collector.ensure_youtube_source()

        def mock_fetch_fail(url):
            raise youtube_collector.YouTubeFetchError("Connection refused")

        channels = [{"name": "JoyNews", "channel_id": "UC_invalid"}]
        res = youtube_collector.collect_youtube(source, channels=channels, fetch=mock_fetch_fail, now=self.now)

        self.assertEqual(res.result, PollRun.Result.FAILED)
        self.assertIn("Connection refused", res.note)
