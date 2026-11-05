import json
import os
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from io import StringIO

from desk import alerts, clock, trends
from desk.collectors import rss
from desk.ingest import replay
from desk.models import Item, Platform, Source, Topic, TrendAlert, TrendCalculation, TrendRow


class TrendAlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)
        rss.ensure_topics()
        User = get_user_model()
        cls.ama = User.objects.get(username="ama")  # Duty editor
        cls.kwame = User.objects.get(username="kwame")  # Analyst

    def setUp(self):
        self.calc = trends.latest()
        self.topic = Topic.objects.get(slug="electricity-tariff")

    def test_classify_breakout_rules(self):
        # 1. Below threshold (<5) -> Not breakout
        r1 = TrendRow(topic=self.topic, current_count=4, previous_count=0, change=4, platforms=["news"])
        ok, alert_type, tier = alerts.classify_breakout(r1)
        self.assertFalse(ok)

        # 2. No increase (change <= 0) -> Not breakout
        r2 = TrendRow(topic=self.topic, current_count=8, previous_count=8, change=0, platforms=["news", "x"])
        ok, alert_type, tier = alerts.classify_breakout(r2)
        self.assertFalse(ok)

        # 3. Single platform, small change -> Not breakout
        r3 = TrendRow(topic=self.topic, current_count=6, previous_count=4, change=2, platforms=["news"])
        ok, alert_type, tier = alerts.classify_breakout(r3)
        self.assertFalse(ok)

        # 4. Cross-network breakout: 2 platforms, small change (+2)
        r4 = TrendRow(topic=self.topic, current_count=6, previous_count=4, change=2, platforms=["news", "x"])
        ok, alert_type, tier = alerts.classify_breakout(r4)
        self.assertTrue(ok)
        self.assertEqual(alert_type, TrendAlert.AlertType.CROSS_NETWORK)
        self.assertEqual(tier, "breakout")

        # 5. Velocity surge: 1 platform, large change (+6)
        r5 = TrendRow(topic=self.topic, current_count=10, previous_count=4, change=6, platforms=["news"])
        ok, alert_type, tier = alerts.classify_breakout(r5)
        self.assertTrue(ok)
        self.assertEqual(alert_type, TrendAlert.AlertType.VELOCITY_SURGE)
        self.assertEqual(tier, "surge_med")

        # 6. Full breakout: 2 platforms, large change (+12)
        r6 = TrendRow(topic=self.topic, current_count=16, previous_count=4, change=12, platforms=["news", "youtube"])
        ok, alert_type, tier = alerts.classify_breakout(r6)
        self.assertTrue(ok)
        self.assertEqual(alert_type, TrendAlert.AlertType.BREAKOUT)
        self.assertEqual(tier, "surge_high")

    def test_format_trend_alert_contains_details(self):
        row = self.calc.rows.get(topic__slug="electricity-tariff")
        # In sample fixture, electricity-tariff has current_count=12, previous_count=4, change=8
        text = alerts.format_trend_alert(row, self.calc, alert_type=TrendAlert.AlertType.BREAKOUT,
                                         base_url="https://desk.npp.org.gh")
        self.assertIn("KEY TRENDING BREAKOUT", text)
        self.assertIn(self.topic.name, text)
        self.assertIn("12", text)
        self.assertIn("+8", text)
        self.assertIn("https://desk.npp.org.gh/trends/electricity-tariff/", text)

    def test_dispatch_trend_alert_disabled_when_credentials_missing(self):
        row = self.calc.rows.get(topic__slug="electricity-tariff")
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            alert = alerts.dispatch_trend_alert(row, self.calc)
            self.assertIsNotNone(alert)
            self.assertEqual(alert.status, TrendAlert.Status.DISABLED)
            self.assertIn("disabled", alert.error_message.lower())

    @patch("desk.notifications.urllib.request.urlopen")
    def test_dispatch_trend_alert_success_and_deduplication(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 998877}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        row = self.calc.rows.get(topic__slug="electricity-tariff")
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"}):
            # 1. First dispatch
            alert1 = alerts.dispatch_trend_alert(row, self.calc)
            self.assertIsNotNone(alert1)
            self.assertEqual(alert1.status, TrendAlert.Status.SENT)
            self.assertEqual(alert1.external_message_id, "998877")
            self.assertEqual(mock_urlopen.call_count, 1)

            # 2. Second dispatch in same hour window with same tier -> deduplicated, does not call Telegram again
            alert2 = alerts.dispatch_trend_alert(row, self.calc)
            self.assertEqual(alert1.pk, alert2.pk)
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_detect_and_dispatch_trend_alerts_scans_calculation(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            alerts_list = alerts.detect_and_dispatch_trend_alerts(self.calc)
            # Electricity tariff in sample fixture has count 12 vs 4 (+8), so it qualifies!
            self.assertTrue(any(a.topic.slug == "electricity-tariff" for a in alerts_list))

    @override_settings(DESK_SAMPLE_MODE=False)  # live commands refuse to run in sample mode
    def test_scan_networks_management_command(self):
        out = StringIO()
        call_command("scan_networks", no_news=True, no_social=True, no_push=True, stdout=out)
        output = out.getvalue()
        self.assertIn("Cross-Network Spike & Breakout Detection", output)
        self.assertIn("Ranked", output)

    def test_source_submit_web_view_get_and_post(self):
        self.client.force_login(self.kwame)
        # 1. GET form
        resp = self.client.get(reverse("desk:source_submit"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Submit Social Observation")

        # 2. POST submission (e.g. Facebook post mentioning ECG and Dumsor)
        post_data = {
            "platform": "facebook",
            "account": "Kumasi Central Market Women",
            "url": "https://www.facebook.com/market/posts/101",
            "title": "ECG power cuts impacting cold store operations",
            "text": "ECG has taken the light again since morning. Dumsor is killing businesses in Kumasi.",
            "language": "en",
            "recompute": "1",
        }
        post_resp = self.client.post(reverse("desk:source_submit"), data=post_data)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, "Successfully recorded Facebook observation")
        dumsor_topic = Topic.objects.get(slug="dumsor")
        self.assertContains(post_resp, dumsor_topic.name)

        # Confirm item was created and auto-tagged in DB
        created_item = Item.objects.filter(url="https://www.facebook.com/market/posts/101").first()
        self.assertIsNotNone(created_item)
        self.assertEqual(created_item.source.platform, Platform.FACEBOOK)
        self.assertTrue(created_item.topics.filter(slug="dumsor").exists())

    def test_overview_displays_breakout_banner(self):
        self.client.force_login(self.ama)
        resp = self.client.get(reverse("desk:overview"))
        self.assertEqual(resp.status_code, 200)
        # In sample shift, electricity-tariff is a breakout (+8 change, 12 mentions)
        self.assertContains(resp, f"Trending Breakout: {self.topic.name}")
        self.assertContains(resp, "Submit observation")
