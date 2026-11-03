from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from desk import coverage, trends
from desk.ingest import replay
from desk.models import Case, CaseEvent, Document, Item, Source


def snapshot():
    calc = trends.latest()
    return {
        "items": Item.objects.count(),
        "origins": Item.objects.filter(origin__isnull=True).count(),
        "ranking": list(calc.rows.filter(rank__isnull=False).order_by("rank")
                        .values_list("topic__slug", "current_count", "previous_count", "change")),
        "queue": list(Case.objects.exclude(status=Case.Status.CLOSED).order_by("due_at").values_list("ref", "owner__username", "status")),
    }


class SampleShiftTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.stats = replay(settings.DESK_FIXTURE_DIR)
        User = get_user_model()
        cls.ama = User.objects.get(username="ama")
        cls.kwame = User.objects.get(username="kwame")

    # --- data and ranking -------------------------------------------------
    def test_replay_skips_repeated_entries(self):
        self.assertEqual(self.stats["items_new"], 95)
        self.assertEqual(self.stats["items_repeated"], 3)

    def test_tariff_rises_from_4_to_12_on_news_and_x(self):
        row = trends.latest().rows.get(topic__slug="electricity-tariff")
        self.assertEqual((row.previous_count, row.current_count, row.change, row.rank), (4, 12, 8, 1))
        self.assertEqual(row.platform_counts, {"news": 7, "x": 5})
        self.assertEqual(row.observed_label, "News + X")
        self.assertEqual(row.partial_platforms, ["x"])
        self.assertEqual(row.buckets, [0, 1, 0, 1, 1, 1, 1, 1, 2, 3, 2, 3])

    def test_ranking_and_tie_breaks_match_the_desk(self):
        calc = trends.latest()
        ranked = [r.topic.slug for r in calc.rows.filter(rank__isnull=False).order_by("rank")]
        self.assertEqual(ranked, ["electricity-tariff", "teacher-allowance", "galamsey", "npp-primary", "black-stars", "dumsor-kumasi"])
        self.assertTrue(calc.rows.get(topic__slug="teacher-allowance").is_new)
        self.assertEqual(calc.rows.get(topic__slug="dumsor-kumasi").observed_label, "X + Facebook links")
        self.assertEqual(calc.below_threshold, 2)

    def test_grouped_copies_and_tips_do_not_count(self):
        post = Item.objects.get(author="@AccraVoices", origin__isnull=True)
        self.assertEqual(post.copies.count(), 13)
        self.assertTrue(Item.objects.filter(source__kind=Source.Kind.TIPS, topics__slug="electricity-tariff").exists())
        self.assertEqual(trends.latest().rows.get(topic__slug="electricity-tariff").current_count, 12)

    def test_quiet_and_delayed_sources_are_reported_differently(self):
        cov = coverage.coverage(trends.latest().as_of)
        rows = {r["name"]: r for r in cov["rows"]}
        self.assertEqual(rows["News feeds"]["status"], "current")
        self.assertEqual(rows["News feeds"]["check"], "Checked at 10:35 GMT · no new items")
        self.assertEqual(rows["X"]["status"], "delayed")
        self.assertEqual(rows["X"]["check"], "Last successful check 09:40 GMT · delayed")
        self.assertEqual(rows["YouTube"]["check"], "Checked at 10:30 GMT · no new items")
        self.assertEqual({s["status"]: s["count"] for s in cov["summary"]},
                         {"current": 2, "delayed": 1, "manual": 2, "awaiting": 2, "tips": 1})

    def test_replay_after_restart_changes_nothing(self):
        before = snapshot()
        stats = replay(settings.DESK_FIXTURE_DIR)
        self.assertEqual((stats["items_new"], stats["cases_new"]), (0, 0))
        self.assertEqual(snapshot(), before)

    # --- review flow --------------------------------------------------------
    def test_full_review_flow_persists_owner_and_decision(self):
        c = self.client
        c.force_login(self.kwame)
        c.post(reverse("desk:issue_take", args=["ISS-0412"]))
        case = Case.objects.get(ref="ISS-0412")
        self.assertEqual((case.owner, case.status, case.verification), (self.kwame, "in_review", "in_review"))

        notice = Document.objects.get(key="sample-tariff-notice-2026-10-28")
        c.post(reverse("desk:issue_evidence", args=["ISS-0412"]), {"document": notice.pk, "stance": "primary"})
        c.post(reverse("desk:issue_translation", args=["ISS-0412"]), {"translation": "The electricity bill goes up from today!"})
        evidence = case.evidence.get()
        c.post(reverse("desk:issue_finding", args=["ISS-0412"]), {
            "finding": "not_supported", "rationale": "The notice dated 28 Oct 2026 sets 1 December 2026.", "cite": [evidence.pk]})
        case.refresh_from_db()
        self.assertEqual((case.status, case.verification), ("reviewed", "not_supported"))
        self.assertTrue(case.evidence.get().cited)
        self.assertEqual(case.origin_item.translation_status, "reviewed")

        c.force_login(self.ama)
        response = c.post(reverse("desk:issue_decision", args=["ISS-0412"]), {"action": "approve", "next_action": "Publish the correction note."})
        self.assertRedirects(response, reverse("desk:overview"))
        case.refresh_from_db()
        self.assertEqual((case.decision, case.decision_by), ("approved", self.ama))

        actions = list(case.events.values_list("actor__username", "role_label", "action"))
        self.assertIn(("kwame", "Analyst", "Took ownership."), actions)
        self.assertIn(("kwame", "Analyst", "Submitted finding: Not supported."), actions)
        self.assertIn(("ama", "Duty editor", "Approved the finding: Not supported."), actions)

        page = c.get(reverse("desk:overview")).content.decode()
        self.assertIn("Kwame Mensah", page)
        self.assertIn("Editor approved finding · A. Owusu", page)

        before = snapshot()
        replay(settings.DESK_FIXTURE_DIR)
        self.assertEqual(snapshot(), before)
        self.assertEqual(Case.objects.get(ref="ISS-0412").decision, "approved")

    def test_analyst_cannot_decide(self):
        self.client.force_login(self.kwame)
        response = self.client.post(reverse("desk:issue_decision", args=["ISS-0398"]), {"action": "approve"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Case.objects.get(ref="ISS-0398").decision, "")
        self.assertFalse(CaseEvent.objects.filter(case__ref="ISS-0398", action__startswith="Approved").exists())

    def test_only_the_owner_submits_a_finding(self):
        self.client.force_login(self.kwame)  # ISS-0415 belongs to Yaw Boateng
        self.client.post(reverse("desk:issue_finding", args=["ISS-0415"]), {"finding": "supported", "rationale": "x"})
        self.assertEqual(Case.objects.get(ref="ISS-0415").verification, "unverified")

    def test_escalate_needs_a_reason_and_close_reopen_keeps_finding(self):
        self.client.force_login(self.ama)
        self.client.post(reverse("desk:issue_decision", args=["ISS-0398"]), {"action": "escalate", "note": ""})
        self.assertEqual(Case.objects.get(ref="ISS-0398").urgency, "l2")
        self.client.post(reverse("desk:issue_decision", args=["ISS-0398"]), {"action": "close"})
        self.client.post(reverse("desk:issue_decision", args=["ISS-0398"]), {"action": "reopen"})
        case = Case.objects.get(ref="ISS-0398")
        self.assertEqual((case.status, case.verification, case.decision), ("in_review", "partly", "reopened"))
        self.assertTrue(case.finding_rationale)

    def test_open_for_review_reuses_the_case_for_a_copy(self):
        self.client.force_login(self.kwame)
        copy = Item.objects.filter(origin__author="@AccraVoices").first()
        response = self.client.post(reverse("desk:issue_new"), {"item": copy.pk})
        self.assertRedirects(response, reverse("desk:issue_detail", args=["ISS-0412"]))
        item = Item.objects.get(author="@KumasiWatch", origin__isnull=True)
        response = self.client.post(reverse("desk:issue_new"), {"item": item.pk})
        new = Case.objects.get(origin_item=item)
        self.assertRedirects(response, reverse("desk:issue_detail", args=[new.ref]))
        self.assertEqual(new.ref, "ISS-0416")

    def test_pages_require_sign_in(self):
        response = self.client.get(reverse("desk:overview"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('desk:overview')}")

    @override_settings(DESK_SAMPLE_MODE=False)
    def test_role_switch_is_off_outside_sample_mode(self):
        response = self.client.post(reverse("desk:sample_role"), {"username": "ama"})
        self.assertEqual(response.status_code, 404)

    def test_queue_and_trend_partials_render(self):
        self.client.force_login(self.ama)
        for name in ("overview_trends_part", "overview_queue_part"):
            self.assertEqual(self.client.get(reverse(f"desk:{name}")).status_code, 200)
