"""Trend windows (architecture.md, "From observation to trend").

At a calculation time T the current window is [T - 60 min, T) and the previous window is
[T - 120 min, T - 60 min); the end of each window is excluded so no item counts twice.
Only distinct items count: syndicated or repeated copies are grouped under their origin,
and WhatsApp tips never count. An item's time is its publication time, or its collection
time when no publication time is known.

Rising topics with at least DESK_MIN_MENTIONS in the current window are ranked by the
increase in count, then by the number of platforms observed, then by the current count.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models.functions import Coalesce

from .coverage import partial_platforms
from .models import Item, Platform, Source, Topic, TrendCalculation, TrendRow

BUCKET_MINUTES = 10
PLATFORM_ORDER = [p.value for p in Platform]
LABELS = dict(Platform.choices)


def observed_label(platforms, manual):
    parts = []
    for platform in platforms:
        label = LABELS[platform]
        parts.append(f"{label} links" if platform in manual else label)
    return " + ".join(parts)


def windows(as_of, window_minutes=None):
    window = timedelta(minutes=window_minutes or settings.DESK_WINDOW_MINUTES)
    return {"previous": (as_of - 2 * window, as_of - window), "current": (as_of - window, as_of)}


@transaction.atomic
def compute(as_of, window_minutes=None, min_mentions=None):
    window_minutes = window_minutes or settings.DESK_WINDOW_MINUTES
    min_mentions = min_mentions or settings.DESK_MIN_MENTIONS
    w = windows(as_of, window_minutes)
    prev_start, cur_start = w["previous"][0], w["current"][0]
    n_buckets = 2 * window_minutes // BUCKET_MINUTES

    items = (
        Item.objects.filter(origin__isnull=True, collected_at__lte=as_of)
        .exclude(source__kind=Source.Kind.TIPS)
        .annotate(observed=Coalesce("published_at", "collected_at"))
        .filter(observed__gte=prev_start, observed__lt=as_of)
        .select_related("source")
        .prefetch_related("topics")
    )
    stats = defaultdict(lambda: {"cur": 0, "prev": 0, "platforms": Counter(), "manual": set(),
                                 "buckets": [0] * n_buckets})
    for item in items:
        bucket = int((item.observed - prev_start).total_seconds() // (BUCKET_MINUTES * 60))
        for topic in item.topics.all():
            s = stats[topic.pk]
            s["buckets"][bucket] += 1
            if item.observed >= cur_start:
                s["cur"] += 1
                s["platforms"][item.source.platform] += 1
                if item.source.kind == Source.Kind.MANUAL:
                    s["manual"].add(item.source.platform)
            else:
                s["prev"] += 1

    partial = partial_platforms(cur_start, as_of)
    calc, _ = TrendCalculation.objects.update_or_create(
        as_of=as_of,
        defaults={"window_minutes": window_minutes, "min_mentions": min_mentions,
                  "partial_platforms": sorted(partial, key=PLATFORM_ORDER.index)},
    )
    calc.rows.all().delete()

    rows = []
    for topic in Topic.objects.filter(pk__in=stats.keys()):
        s = stats[topic.pk]
        platforms = sorted(s["platforms"], key=PLATFORM_ORDER.index)
        rows.append(TrendRow(
            calculation=calc, topic=topic, current_count=s["cur"], previous_count=s["prev"],
            change=s["cur"] - s["prev"], platforms=platforms,
            platform_counts={p: s["platforms"][p] for p in platforms},
            partial_platforms=[p for p in platforms if p in partial],
            observed_label=observed_label(platforms, s["manual"]) or "No observations this hour",
            buckets=s["buckets"],
        ))
    eligible = [r for r in rows if r.current_count >= min_mentions and r.change > 0]
    eligible.sort(key=lambda r: (-r.change, -len(r.platforms), -r.current_count, r.topic.name))
    for rank, row in enumerate(eligible, start=1):
        row.rank = rank
    calc.below_threshold = sum(1 for r in rows if r.rank is None and r.current_count > 0)
    calc.save(update_fields=["below_threshold"])
    TrendRow.objects.bulk_create(rows)
    return calc


def latest():
    return TrendCalculation.objects.first()


def prune(days=7, as_of=None):
    """Delete trend calculations older than retention threshold (default 7 days)."""
    now = as_of or latest()
    if now and hasattr(now, "as_of"):
        now_dt = now.as_of
    else:
        from django.utils import timezone
        now_dt = timezone.now()
    cutoff = now_dt - timedelta(days=days)
    deleted, _ = TrendCalculation.objects.filter(as_of__lt=cutoff).delete()
    return deleted
