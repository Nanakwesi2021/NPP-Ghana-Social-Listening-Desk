"""Live news collector, tested offline against saved feeds in tests/fixtures/rss."""
import http.client
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from desk import coverage, tagging, trends
from desk.collectors import rss
from desk.models import Item, PollRun, Topic

FIXTURES = settings.REPO_ROOT / "tests" / "fixtures" / "rss"
T0 = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
REAL_CONFIG = rss.load_config()
# Tests use their own outlet list so editing live_config.json never changes their meaning.
TEST_CONFIG = {"topics": REAL_CONFIG["topics"], "feeds": [
    {"key": "citi-newsroom", "name": "Citi Newsroom", "url": "https://example.org/feeds/a.xml"},
    {"key": "joy-online", "name": "Joy Online", "url": "https://example.org/feeds/b.xml"},
    {"key": "daily-graphic", "name": "Daily Graphic", "url": "https://example.org/feeds/c.xml"},
    {"key": "peace-fm-online", "name": "Peace FM Online", "url": "https://example.org/feeds/d.xml"},
]}
URLS = {f["key"]: f["url"] for f in TEST_CONFIG["feeds"]}


def fetcher(plan):
    """plan maps a source key to a fixture file name, raw bytes or an exception."""
    by_url = {URLS[key]: value for key, value in plan.items()}

    def fetch(url):
        value = by_url[url]
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, bytes) else (FIXTURES / value).read_bytes()
    return fetch


HEALTHY = {"citi-newsroom": "citi_pass1.xml", "joy-online": "joy_no_dates.xml",
           "daily-graphic": "graphic_malformed.xml", "peace-fm-online": rss.FetchError("HTTP 500")}


class CollectorTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(rss, "load_config", return_value=TEST_CONFIG)
        patcher.start()
        self.addCleanup(patcher.stop)
        rss.ensure_topics()
        self.sources = {s.key: s for s in rss.ensure_sources()}

    def run_pass(self, plan, at=T0):
        return {r.source.key: r for r in rss.collect(list(self.sources.values()), fetch=fetcher(plan), now=at)}

    def test_one_pass_records_each_feed_and_isolates_failures(self):
        results = self.run_pass(HEALTHY)
        self.assertEqual((results["citi-newsroom"].result, results["citi-newsroom"].new_items), ("complete", 3))
        self.assertEqual((results["joy-online"].result, results["joy-online"].new_items), ("complete", 2))
        self.assertEqual(results["daily-graphic"].result, "failed")
        self.assertIn("Not a feed: the address returned a web page", results["daily-graphic"].note)
        self.assertEqual((results["peace-fm-online"].result, results["peace-fm-online"].note), ("failed", "HTTP 500"))
        self.assertEqual(PollRun.objects.filter(finished_at=T0).count(), 4)
        self.assertEqual(Item.objects.count(), 5)

    def test_recollecting_adds_only_new_items(self):
        self.run_pass(HEALTHY)
        again = self.run_pass(HEALTHY, at=T0 + timedelta(minutes=5))
        self.assertEqual(again["citi-newsroom"].new_items, 0)
        later = self.run_pass({**HEALTHY, "citi-newsroom": "citi_pass2.xml"}, at=T0 + timedelta(minutes=10))
        self.assertEqual(later["citi-newsroom"].new_items, 1)
        self.assertEqual(Item.objects.filter(source__key="citi-newsroom").count(), 4)
        first = Item.objects.get(external_id="https://example.org/sample/outlet-a/?p=1001")
        self.assertEqual(first.collected_at, T0)  # the first collection time is kept

    def test_missing_date_and_missing_guid(self):
        self.run_pass(HEALTHY)
        undated = Item.objects.get(url="https://example.org/sample/outlet-b/galamsey-water")
        self.assertIsNone(undated.published_at)
        self.assertTrue(undated.uses_collection_time)
        no_guid = Item.objects.get(url="https://example.org/sample/outlet-b/teachers")
        self.assertEqual(no_guid.external_id, "https://example.org/sample/outlet-b/teachers")
        self.assertEqual(no_guid.published_at, datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc))

    def test_keyword_rules_tag_items_and_leave_others_untagged(self):
        self.run_pass({**HEALTHY, "citi-newsroom": "citi_pass2.xml"})
        topics = {i.title: sorted(i.topics.values_list("slug", flat=True)) for i in Item.objects.all()}
        self.assertEqual(topics["Regulator publishes quarterly tariff adjustment"], ["electricity-tariff"])
        self.assertEqual(topics["Residents in Kumasi report another night without power"], ["dumsor"])
        self.assertEqual(topics["NPP national council to meet on primary timetable"], ["npp-party-affairs"])
        self.assertEqual(topics["Galamsey: water utility cuts output as river turbidity rises"], ["galamsey"])
        self.assertEqual(topics["Teachers' unions press for allowance arrears"], ["schools-teachers"])
        rules = tagging.compile_rules()
        self.assertEqual(tagging.matching_topics("The ecg reading was normal", rules), [])
        self.assertEqual([t.slug for t in tagging.matching_topics("ECG fault on a feeder line", rules)], ["dumsor"])
        self.assertEqual(tagging.matching_topics("A quiet day in parliament", rules), [])

    def test_retag_applies_edited_rules(self):
        self.run_pass(HEALTHY)
        Topic.objects.filter(slug="black-stars").update(keywords="")
        changed = rss.retag(list(self.sources.values()))
        self.assertEqual(changed, 1)
        self.assertFalse(Item.objects.filter(topics__slug="black-stars").exists())

    def test_failed_feed_shows_on_coverage_while_others_stay_current(self):
        self.run_pass(HEALTHY)
        failing_joy = {**HEALTHY, "joy-online": rss.FetchError("HTTP 503")}
        for minutes in (5, 10, 15):
            self.run_pass(failing_joy, at=T0 + timedelta(minutes=minutes))
        as_of = T0 + timedelta(minutes=16)
        states = {s.key: coverage.source_state(s, as_of) for s in self.sources.values()}
        self.assertEqual(states["citi-newsroom"]["status"], "current")
        self.assertEqual(states["citi-newsroom"]["check"], "Checked at 10:15 GMT · no new items")
        self.assertEqual(states["joy-online"]["status"], "delayed")
        self.assertEqual(states["joy-online"]["check"], "Last successful check 10:00 GMT · delayed")
        self.assertIn("3 failed polls since 10:00 (HTTP 503)", states["joy-online"]["note"])
        self.assertEqual(states["peace-fm-online"]["status"], "unavailable")
        self.assertIn("failed: HTTP 500", states["peace-fm-online"]["note"])
        cov = coverage.coverage(as_of)
        news = next(r for r in cov["rows"] if r["name"] == "News feeds")
        self.assertEqual(news["status"], "delayed")
        self.assertEqual({s["source"].key for s in cov["delayed"]}, {"joy-online", "daily-graphic", "peace-fm-online"})
        self.assertIn("news", coverage.partial_platforms(as_of - timedelta(hours=1), as_of))

    def test_freshness_reports_median_delay(self):
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>empty</title></channel></rss>'
        self.run_pass({**HEALTHY, "citi-newsroom": empty, "joy-online": empty}, at=T0 - timedelta(minutes=35))
        self.run_pass(HEALTHY)
        citi = coverage.freshness([self.sources["citi-newsroom"]], T0)
        self.assertEqual(citi["text"], "Median delay 10 min over 3 dated items today")  # 20, 10 and 5 minutes
        joy = coverage.freshness([self.sources["joy-online"]], T0)
        self.assertEqual(joy["text"], "Median delay 30 min over 1 dated item today · 1 without a publication date")

    def test_freshness_ignores_the_backlog_present_when_collection_began(self):
        self.run_pass(HEALTHY)  # first ever read at 10:00
        citi = coverage.freshness([self.sources["citi-newsroom"]], T0)
        # 09:40 and 09:50 were backlog; 09:55 falls inside one poll interval of the first read and counts.
        self.assertEqual(citi["text"], "Median delay 5 min over 1 dated item today")
        graphic_like = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title><item><title>Old</title><guid>o1</guid><pubDate>Tue, 03 Nov 2026 06:00:00 +0000</pubDate></item></channel></rss>'
        self.run_pass({**HEALTHY, "daily-graphic": graphic_like}, at=T0)
        self.assertEqual(coverage.freshness([self.sources["daily-graphic"]], T0)["text"],
                         "No items published since collection began at 10:00 GMT")
        self.assertEqual(coverage.freshness([self.sources["peace-fm-online"]], T0)["text"], "No successful check yet")

    def test_trends_recalculate_from_live_items(self):
        items = "".join(
            f"<item><title>Tariff update {i}</title><guid>t{i}</guid><link>https://example.org/t{i}</link>"
            f"<pubDate>Tue, 03 Nov 2026 09:{10 + i * 5:02d}:00 +0000</pubDate></item>" for i in range(6))
        feed = f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{items}</channel></rss>'.encode()
        self.run_pass({**HEALTHY, "citi-newsroom": feed})
        calc = trends.compute(T0)
        row = calc.rows.get(topic__slug="electricity-tariff")
        self.assertEqual((row.rank, row.current_count, row.previous_count, row.observed_label), (1, 6, 0, "News"))
        self.assertEqual(row.partial_platforms, ["news"])  # two outlets failed during the window

    def test_broken_xml_and_truncated_responses_fail_only_that_feed(self):
        truncated = b'<?xml version="1.0"?><rss><channel><item><title>Cut off'
        results = self.run_pass({**HEALTHY, "joy-online": truncated})
        self.assertEqual((results["joy-online"].result, results["joy-online"].note), ("complete", "Parsed with warnings"))
        results = self.run_pass({**HEALTHY, "joy-online": b"\x00\x01 not a feed"}, at=T0 + timedelta(minutes=5))
        self.assertEqual(results["joy-online"].result, "failed")
        self.assertIn("Malformed feed", results["joy-online"].note)
        self.assertEqual(results["citi-newsroom"].result, "complete")
        with mock.patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"partial")):
            with self.assertRaisesMessage(rss.FetchError, "Incomplete response: IncompleteRead"):
                rss.http_fetch("https://example.org/feed")

    def test_wordpress_posts_api_is_read_like_a_feed(self):
        citi = self.sources["citi-newsroom"]
        citi.feed_url = "https://example.org/wp-json/wp/v2/posts?per_page=50&_fields=id,date_gmt,link,title,excerpt"
        citi.save()
        result = rss.collect_source(citi, fetch=lambda url: (FIXTURES / "wp_posts.json").read_bytes(), now=T0)
        self.assertEqual((result.result, result.new_items), ("complete", 3))
        item = Item.objects.get(url="https://example.org/sample/outlet-c/2026/11/ecg-load-shedding/")
        self.assertEqual(item.title, "ECG’s load-shedding timetable – what we know")  # HTML entities decoded
        self.assertEqual(item.published_at, datetime(2026, 11, 3, 9, 45, 12, tzinfo=timezone.utc))
        self.assertEqual(list(item.topics.values_list("slug", flat=True)), ["dumsor"])
        undated = Item.objects.get(external_id="wp-post:303")  # no link: falls back to the post id
        self.assertIsNone(undated.published_at)
        again = rss.collect_source(citi, fetch=lambda url: (FIXTURES / "wp_posts.json").read_bytes(), now=T0 + timedelta(minutes=5))
        self.assertEqual(again.new_items, 0)
        bad = rss.collect_source(citi, fetch=lambda url: b"<html>error</html>", now=T0 + timedelta(minutes=10))
        self.assertEqual((bad.result, bad.note), ("failed", "Not a posts API response: invalid JSON"))

    def test_outlets_without_a_feed_are_not_polled_and_sync_applies_config(self):
        sources = rss.ensure_sources(config=REAL_CONFIG, sync=True)
        by_key = {s.key: s for s in sources}
        self.assertIn("/wp-json/wp/v2/posts", by_key["citi-newsroom"].feed_url)
        peace = by_key["peace-fm-online"]
        self.assertEqual((peace.kind, peace.feed_url), ("awaiting", ""))
        polled = []
        rss.collect(sources, fetch=lambda url: polled.append(url) or b"<rss version='2.0'><channel></channel></rss>", now=T0)
        self.assertEqual(len(polled), 3)
        self.assertFalse(PollRun.objects.filter(source=peace).exists())
        self.assertEqual(coverage.source_state(peace, T0)["status"], "awaiting")
        unsynced = rss.ensure_sources(config=TEST_CONFIG)  # without sync, existing outlets keep their settings
        self.assertIn("/wp-json/", {s.key: s for s in unsynced}["citi-newsroom"].feed_url)

    def test_collect_news_command_uses_the_same_isolation(self):
        out = StringIO()
        with mock.patch("desk.collectors.rss.http_fetch", fetcher(HEALTHY)):
            call_command("collect_news", stdout=out)
        text = out.getvalue()
        self.assertIn("Citi Newsroom: 3 new of 4 in feed", text)
        self.assertIn("Peace FM Online: failed · HTTP 500", text)
        call_command("recompute_trends", as_of="2026-11-03T10:00:00Z", stdout=out)
        self.assertIn("Windows ending 10:00 GMT", out.getvalue())
