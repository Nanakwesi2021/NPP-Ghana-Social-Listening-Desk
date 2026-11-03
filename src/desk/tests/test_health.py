"""/healthz/ for uptime monitors (desk/health.py)."""
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from desk.models import PollRun, Source, TrendCalculation


@override_settings(DESK_SAMPLE_MODE=False, DESK_HEALTH_MAX_TREND_AGE_MINUTES=5, DESK_HEALTH_MAX_POLL_AGE_MINUTES=20)
class HealthTests(TestCase):
    def setUp(self):
        self.source = Source.objects.create(key="n", name="Outlet", group="News feeds", platform="news",
                                            kind="collected", method="RSS", scope="")

    def fresh(self, trend_minutes=1, poll_minutes=3):
        now = timezone.now()
        calc = TrendCalculation.objects.create(as_of=now, window_minutes=60, min_mentions=5)
        TrendCalculation.objects.filter(pk=calc.pk).update(computed_at=now - timedelta(minutes=trend_minutes))
        PollRun.objects.create(source=self.source, finished_at=now - timedelta(minutes=poll_minutes), result="complete")

    def get(self):
        return self.client.get(reverse("healthz"))

    def test_healthy_live_desk(self):
        self.fresh()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response["Cache-Control"].split(",")[0].strip(), "max-age=0")

    def test_stopped_worker_is_reported(self):
        self.fresh(trend_minutes=12, poll_minutes=40)
        response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"]["trends"], "stale")
        self.assertEqual(response.json()["checks"]["collection"], "stale")

    def test_new_desk_with_nothing_collected_is_not_healthy(self):
        self.assertEqual(self.get().status_code, 503)

    def test_database_failure(self):
        with mock.patch("desk.health.connection.cursor", side_effect=DatabaseError("down")):
            response = self.get()
        self.assertEqual((response.status_code, response.json()["status"]), (503, "down"))

    def test_needs_no_sign_in_and_reveals_no_desk_content(self):
        self.fresh()
        body = self.get().content.decode()
        self.assertNotIn("Outlet", body)
        self.assertEqual(set(self.get().json()), {"status", "checks"})

    @override_settings(DESK_SAMPLE_MODE=True)
    def test_sample_mode_only_checks_the_database(self):
        response = self.get()
        self.assertEqual((response.status_code, response.json()["checks"]), (200, {"database": "ok"}))
