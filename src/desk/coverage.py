"""Source status: what the desk can see at a given time.

A collected source is delayed after two poll intervals without a complete poll. A capped or
failed poll inside a trend window makes that window partial for the source's platform.
Quiet (a complete poll with no new items) and missing coverage are reported differently.
"""
import statistics
from collections import OrderedDict
from datetime import timedelta, timezone as dt_timezone

from .models import Item, PollRun, Source

STATUS_ORDER = ["delayed", "unavailable", "current", "manual", "awaiting", "tips"]
STATUS_LABELS = {
    "current": "Current",
    "delayed": "Delayed",
    "manual": "Manual links",
    "awaiting": "Awaiting access",
    "tips": "Tips only",
    "unavailable": "Not collecting",
}


def hm(dt):
    return dt.astimezone(dt_timezone.utc).strftime("%H:%M")


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def source_state(source, as_of):
    """Status, the last-check sentence and its note for one source."""
    state = {"source": source, "status": "", "check": "", "note": "", "partial": False}
    if source.kind == Source.Kind.AWAITING:
        state.update(status="awaiting", check="Never checked")
        return state
    if source.kind in (Source.Kind.MANUAL, Source.Kind.TIPS):
        items = source.items.filter(collected_at__lte=as_of, collected_at__date=as_of.date())
        latest = items.order_by("-collected_at").first()
        word = "tip" if source.kind == Source.Kind.TIPS else "link"
        if latest is None:
            state.update(status=source.kind if source.kind == Source.Kind.TIPS else "manual",
                         check=f"No {word}s submitted today")
            return state
        count = items.count()
        if source.kind == Source.Kind.TIPS:
            state.update(status="tips", check=f"Last tip received {hm(latest.collected_at)} GMT",
                         note=f"{_plural(count, 'tip')} today · not counted in trends")
        else:
            state.update(status="manual", check=f"Last link added {hm(latest.collected_at)} GMT",
                         note=f"{_plural(count, 'link')} today")
        return state

    polls = source.polls.filter(finished_at__lte=as_of)
    last = polls.first()
    last_complete = polls.filter(result=PollRun.Result.COMPLETE).first()
    if last_complete is None:
        note = f"Last attempt {hm(last.finished_at)} GMT failed: {last.note}" if last and last.note else ""
        state.update(status="unavailable", check="No successful check yet", note=note, partial=True)
        return state
    allowed = timedelta(minutes=2 * (source.poll_interval_minutes or 5))
    if as_of - last_complete.finished_at > allowed:
        since = polls.filter(finished_at__gt=last_complete.finished_at)
        capped = since.filter(result=PollRun.Result.CAPPED).count()
        failed = since.filter(result=PollRun.Result.FAILED).count()
        parts = []
        if capped:
            parts.append(_plural(capped, "capped poll"))
        if failed:
            parts.append(_plural(failed, "failed poll"))
        missed = " and ".join(parts) or "No polls"
        reason = f" ({last.note})" if last and last.result == PollRun.Result.FAILED and last.note else ""
        state.update(
            status="delayed",
            check=f"Last successful check {hm(last_complete.finished_at)} GMT · delayed",
            note=f"{missed} since {hm(last_complete.finished_at)}{reason} · windows marked partial",
            partial=True,
            since=hm(last_complete.finished_at),
        )
        return state
    new = last.new_items if last else 0
    check = f"Checked at {hm(last.finished_at)} GMT · " + ("no new items" if new == 0 else _plural(new, "new item"))
    state.update(status="current", check=check)
    return state


def freshness(sources, as_of):
    """Publication-to-collection delay for today's distinct items from these sources.

    Only items published after a source's first complete poll count, so the backlog a feed
    already held when collection began does not inflate the delay.
    """
    delays, undated, started = [], 0, []
    for source in sources:
        first = source.polls.filter(result=PollRun.Result.COMPLETE, finished_at__lte=as_of).order_by("finished_at").first()
        if first is None:
            continue
        started.append(first.finished_at)
        since = first.finished_at - timedelta(minutes=source.poll_interval_minutes or 5)
        items = Item.objects.filter(source=source, origin__isnull=True, collected_at__lte=as_of,
                                    collected_at__date=as_of.date()).values_list("published_at", "collected_at")
        for published, collected in items:
            if published is None:
                undated += 1
            elif published >= since:
                delays.append(max(0.0, (collected - published).total_seconds() / 60))
    if not delays:
        if not started:
            text = "No successful check yet"
        elif undated:
            text = f"{_plural(undated, 'item')} today, none with a publication date"
        else:
            text = f"No items published since collection began at {hm(min(started))} GMT"
        return {"median": None, "count": 0, "undated": undated, "text": text}
    median = statistics.median(delays)
    text = f"Median delay {round(median)} min over {_plural(len(delays), 'dated item')} today"
    if undated:
        text += f" · {undated} without a publication date"
    return {"median": median, "count": len(delays), "undated": undated, "text": text}


def partial_platforms(start, end):
    """Platforms whose collected coverage was incomplete at any point in [start, end)."""
    partial = set()
    for source in Source.objects.filter(kind=Source.Kind.COLLECTED):
        if source_state(source, end)["partial"]:
            partial.add(source.platform)
        elif source.polls.filter(finished_at__gte=start, finished_at__lt=end).exclude(
            result=PollRun.Result.COMPLETE
        ).exists():
            partial.add(source.platform)
    return partial


def coverage(as_of):
    """Source groups for the coverage page, in configured order, with a summary count."""
    groups = OrderedDict()
    for source in Source.objects.all():
        state = source_state(source, as_of)
        state["label"] = STATUS_LABELS[state["status"]]
        if source.kind == Source.Kind.COLLECTED:
            state["freshness"] = freshness([source], as_of)["text"]
        groups.setdefault(source.group, []).append(state)
    rows = []
    for name, states in groups.items():
        status = min((s["status"] for s in states), key=STATUS_ORDER.index)
        first = states[0]
        row = {"name": name, "status": status, "label": STATUS_LABELS[status], "members": states,
               "source": first["source"], "check": first["check"], "note": first["note"]}
        if first["source"].kind == Source.Kind.COLLECTED:
            row["freshness"] = freshness([s["source"] for s in states], as_of)["text"]
        if len(states) > 1:
            current = sum(1 for s in states if s["status"] == "current")
            worst = next((s for s in states if s["status"] == status), first)
            row["check"] = worst["check"]
            row["note"] = f"{current} of {len(states)} outlets current"
            row["detail"] = f"{len(states)} outlets"
        else:
            row["detail"] = first["source"].detail
        rows.append(row)
    summary = OrderedDict((key, 0) for key in ["current", "delayed", "manual", "awaiting", "tips", "unavailable"])
    for row in rows:
        summary[row["status"]] += 1
    summary = [{"status": k, "label": STATUS_LABELS[k], "count": v} for k, v in summary.items() if v]
    # Collected sources the desk cannot currently rely on: delayed, or never checked successfully.
    delayed = [s for row in rows for s in row["members"]
               if s["status"] == "delayed" or (s["status"] == "unavailable" and s["source"].kind == Source.Kind.COLLECTED)]
    return {"rows": rows, "summary": summary, "delayed": delayed}


def platform_states(as_of):
    """Best status per platform, for the trend detail breakdown."""
    states = {}
    for source in Source.objects.all():
        state = source_state(source, as_of)
        current = states.get(source.platform)
        if current is None or STATUS_ORDER.index(state["status"]) < STATUS_ORDER.index(current["status"]):
            states[source.platform] = state
    return states


def latest_tip_count(topic, start, end):
    return Item.objects.filter(
        topics=topic, source__kind=Source.Kind.TIPS, collected_at__gte=start, collected_at__lt=end
    ).count()
