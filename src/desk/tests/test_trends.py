from datetime import datetime, timedelta, timezone

from django.test import TestCase

from desk import trends
from desk.models import Item, PollRun, Source, Topic

AS_OF = datetime(2026, 11, 3, 10, 37, tzinfo=timezone.utc)


def at(minutes_before):
    return AS_OF - timedelta(minutes=minutes_before)


class WindowTests(TestCase):
    """Synthetic data: one news outlet, one topic per test."""

    def setUp(self):
        self.news = Source.objects.create(key="n", name="Outlet", group="News feeds", platform="news", kind="collected",
                                          method="RSS", scope="", poll_interval_minutes=5)
        self.x = Source.objects.create(key="x", name="X", group="X", platform="x", kind="collected",
                                       method="API", scope="", poll_interval_minutes=5)
        self.yt = Source.objects.create(key="y", name="YouTube", group="YouTube", platform="youtube", kind="collected",
                                        method="API", scope="", poll_interval_minutes=15)
        for source in (self.news, self.x, self.yt):
            PollRun.objects.create(source=source, finished_at=at(1), result="complete")
        self.n = 0

    def item(self, topic, minutes_before, source=None, published=True, origin=None):
        self.n += 1
        when = at(minutes_before)
        item = Item.objects.create(source=source or self.news, external_id=f"i{self.n}", url="https://example.org/i",
                                   author="a", excerpt="e", published_at=when if published else None,
                                   collected_at=when, origin=origin)
        item.topics.add(topic)
        return item

    def topic(self, slug):
        return Topic.objects.create(slug=slug, name=slug.title())

    def row(self, calc, topic):
        return calc.rows.get(topic=topic)

    def test_window_bounds_exclude_their_end(self):
        t = self.topic("bounds")
        self.item(t, 0)      # exactly at the calculation time: not counted
        self.item(t, 60)     # start of the current window: current
        self.item(t, 61)     # previous window
        self.item(t, 120)    # start of the previous window: previous
        self.item(t, 121)    # outside both windows
        row = self.row(trends.compute(AS_OF), t)
        self.assertEqual((row.current_count, row.previous_count), (1, 2))

    def test_copies_count_once(self):
        t = self.topic("copies")
        origin = self.item(t, 10)
        for _ in range(5):
            self.item(t, 5, origin=origin)
        row = self.row(trends.compute(AS_OF), t)
        self.assertEqual(row.current_count, 1)

    def test_collection_time_used_when_publication_unknown(self):
        t = self.topic("fallback")
        self.item(t, 30, published=False)
        self.assertEqual(self.row(trends.compute(AS_OF), t).current_count, 1)

    def test_rank_by_increase_then_platforms_then_current_count(self):
        a, b, c, d = (self.topic(s) for s in ("a", "b", "c", "d"))
        for _ in range(6):
            self.item(a, 10)               # +6, one platform
        for _ in range(3):
            self.item(b, 10)
        for _ in range(3):
            self.item(b, 20, source=self.x)  # +6, two platforms
        for _ in range(8):
            self.item(c, 10)
        for _ in range(2):
            self.item(c, 70)               # +6, one platform, higher current count
        for _ in range(4):
            self.item(d, 10)               # below the 5-mention minimum
        calc = trends.compute(AS_OF)
        ranked = [r.topic.slug for r in calc.rows.filter(rank__isnull=False).order_by("rank")]
        self.assertEqual(ranked, ["b", "c", "a"])
        self.assertEqual(calc.below_threshold, 1)

    def test_zero_baseline_is_new(self):
        t = self.topic("new")
        for _ in range(5):
            self.item(t, 10)
        row = self.row(trends.compute(AS_OF), t)
        self.assertTrue(row.is_new)
        self.assertEqual(row.rank, 1)

    def test_capped_poll_marks_platform_partial(self):
        t = self.topic("partial")
        for _ in range(5):
            self.item(t, 10, source=self.x)
        PollRun.objects.create(source=self.x, finished_at=at(20), result="capped")
        row = self.row(trends.compute(AS_OF), t)
        self.assertEqual(row.partial_platforms, ["x"])

    def test_recompute_is_stable(self):
        t = self.topic("stable")
        for _ in range(5):
            self.item(t, 10)
        first = list(trends.compute(AS_OF).rows.values_list("topic__slug", "rank", "current_count"))
        second = list(trends.compute(AS_OF).rows.values_list("topic__slug", "rank", "current_count"))
        self.assertEqual(first, second)

    def test_prune_deletes_historical_calculations(self):
        t = self.topic("prune")
        self.item(t, 10)
        old_time = AS_OF - timedelta(days=10)
        old_calc = trends.compute(old_time)
        recent_calc = trends.compute(AS_OF)

        deleted = trends.prune(days=7, as_of=AS_OF)
        self.assertEqual(deleted, 1)
        self.assertFalse(trends.TrendCalculation.objects.filter(pk=old_calc.pk).exists())
        self.assertTrue(trends.TrendCalculation.objects.filter(pk=recent_calc.pk).exists())
