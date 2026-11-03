from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import clock, coverage, trends, workflow
from .ingest import sample_people
from .models import Case, Document, Evidence, Item, Platform, Source, Subject, Topic, TrendRow
from .trends import PLATFORM_ORDER

SUBJECT_FILTERS = [("all", "All subjects")] + list(Subject.choices)
# Collected platforms first, then submissions, then platforms the desk cannot see yet.
BREAKDOWN_ORDER = ["news", "x", "youtube", "facebook", "tiktok", "instagram", "threads", "whatsapp"]
PLATFORM_FILTERS = [("all", "All platforms")] + [(p, l) for p, l in Platform.choices if p != Platform.WHATSAPP]


def hm(dt):
    return coverage.hm(dt)


def _calc_or_404():
    calc = trends.latest()
    if calc is None:
        raise Http404("No trend calculation yet. Run: python manage.py replay_sample")
    return calc


def _due(case, now):
    minutes = int((case.due_at - now).total_seconds() // 60)
    if case.status == Case.Status.CLOSED:
        return {"text": f"Closed {hm(case.closed_at)} GMT" if case.closed_at else "Closed", "overdue": False}
    if minutes < 0:
        return {"text": f"Overdue · due {hm(case.due_at)} GMT", "overdue": True, "minutes": minutes}
    return {"text": f"Due {hm(case.due_at)} GMT", "overdue": False, "minutes": minutes,
            "relative": "now" if minutes == 0 else f"in {minutes} min"}


def _decorate_cases(cases, now):
    cases = list(cases)
    for case in cases:
        case.due = _due(case, now)
        case.decision_line = ""
        if case.decision == Case.Decision.APPROVED and case.decision_by:
            case.decision_line = f"Editor approved finding · {case.decision_by.first_name[:1]}. {case.decision_by.last_name} · {hm(case.decision_at)} GMT"
    return cases


def _windows(calc):
    w = trends.windows(calc.as_of, calc.window_minutes)
    return {"current": f"{hm(w['current'][0])}–{hm(w['current'][1])}", "previous": f"{hm(w['previous'][0])}–{hm(w['previous'][1])}"}


def trend_context(request, calc):
    subject = request.GET.get("subject", "all")
    platform = request.GET.get("platform", "all")
    rows = calc.rows.select_related("topic").filter(rank__isnull=False).order_by("rank")
    if subject != "all":
        rows = rows.filter(topic__subject=subject)
    rows = [r for r in rows if platform == "all" or platform in r.platforms]
    open_cases = dict(
        Case.objects.exclude(status=Case.Status.CLOSED).filter(topic__isnull=False)
        .values_list("topic").annotate(n=Count("id"))
    )
    for row in rows:
        row.open_issues = open_cases.get(row.topic_id, 0)
        row.partial_labels = [dict(Platform.choices)[p] for p in row.partial_platforms]
    delayed = coverage.coverage(calc.as_of)["delayed"]
    return {"calc": calc, "rows": rows, "windows": _windows(calc), "subject": subject, "platform": platform,
            "subject_filters": SUBJECT_FILTERS, "platform_filters": PLATFORM_FILTERS, "delayed_sources": delayed,
            "filtered": subject != "all" or platform != "all"}


def queue_context(now):
    cases = _decorate_cases(
        Case.objects.exclude(status=Case.Status.CLOSED).select_related("owner", "decision_by", "topic").order_by("due_at"),
        now,
    )
    closed_today = Case.objects.filter(status=Case.Status.CLOSED, closed_at__date=now.date()).count()
    return {"cases": cases, "closed_today": closed_today, "now": now}


def _brief(calc, queue, cov):
    top = calc.rows.select_related("topic").filter(rank=1).first()
    cases = queue["cases"]
    need = [c for c in cases if c.decision != Case.Decision.APPROVED]
    critical = sum(1 for c in need if c.urgency == Case.Urgency.CRITICAL)
    urgent = sum(1 for c in need if c.urgency == Case.Urgency.URGENT)
    overdue = [c for c in cases if c.due["overdue"]]
    upcoming = [c for c in cases if not c.due["overdue"]]
    brief = {"top": top, "need": len(need), "open": len(cases), "critical": critical, "urgent": urgent,
             "overdue": overdue, "next_due": upcoming[0] if upcoming else None}
    fresh = []
    for r in cov["rows"]:
        if r["status"] == "current":
            fresh.append((r["name"], r["check"]))
        elif len(r["members"]) > 1:
            fresh += [(m["source"].name, m["check"]) for m in r["members"] if m["status"] == "current"]
    brief["fresh"] = "; ".join(f"{name} {check.split(' · ')[0].replace('Checked at ', 'checked ')}" for name, check in fresh)
    brief["delayed"] = [f"{s['source'].name} delayed since {s['since']}" if s["status"] == "delayed"
                        else f"{s['source'].name} not collecting" for s in cov["delayed"]]
    return brief


@login_required
def overview(request):
    calc = _calc_or_404()
    now = clock.now()
    queue = queue_context(now)
    cov = coverage.coverage(calc.as_of)
    ctx = {**trend_context(request, calc), **queue, "brief": _brief(calc, queue, cov), "nav": "overview"}
    return render(request, "desk/overview.html", ctx)


@login_required
def overview_trends_part(request):
    return render(request, "desk/partials/_trend_panel.html", trend_context(request, _calc_or_404()))


@login_required
def overview_queue_part(request):
    return render(request, "desk/partials/_queue_panel.html", queue_context(clock.now()))


@login_required
def trend_list(request):
    calc = _calc_or_404()
    return render(request, "desk/trend_list.html", {**trend_context(request, calc), "nav": "trends"})


def _representative(items, limit=5):
    chosen = [i for i in items if i.case_count]
    for item in sorted(items, key=lambda i: -i.copy_count):
        if item.copy_count and item not in chosen:
            chosen.append(item)
    pairs = {(i.source.platform, i.language) for i in chosen}
    for item in reversed(items):
        key = (item.source.platform, item.language)
        if key not in pairs and item not in chosen:
            chosen.append(item)
            pairs.add(key)
    for item in reversed(items):
        if item not in chosen:
            chosen.append(item)
    return sorted(chosen[:limit], key=lambda i: i.observed)


@login_required
def trend_detail(request, slug):
    calc = _calc_or_404()
    wanted = request.GET.get("topic")
    if wanted and wanted != slug:
        query = request.GET.copy()
        query.pop("topic")
        return redirect(reverse("desk:trend_detail", args=[wanted]) + (f"?{query.urlencode()}" if query else ""))
    row = get_object_or_404(TrendRow.objects.select_related("topic"), calculation=calc, topic__slug=slug)
    topic = row.topic
    w = trends.windows(calc.as_of, calc.window_minutes)
    cur_start, cur_end = w["current"]
    platform = request.GET.get("platform", "all")
    subject = request.GET.get("subject", "all")
    items = list(
        Item.objects.filter(topics=topic, origin__isnull=True, collected_at__lte=calc.as_of)
        .exclude(source__kind=Source.Kind.TIPS)
        .annotate(observed=Coalesce("published_at", "collected_at"), copy_count=Count("copies", distinct=True),
                  case_count=Count("cases", distinct=True))
        .filter(observed__gte=cur_start, observed__lt=cur_end)
        .select_related("source").order_by("observed")
    )
    if platform != "all":
        items = [i for i in items if i.source.platform == platform]
    show_all = request.GET.get("all") == "1"
    shown = items if show_all else _representative(items)

    states = coverage.platform_states(calc.as_of)
    chip_platforms = [p for p in PLATFORM_ORDER if p in row.platform_counts or (p in states and states[p]["status"] == "current") or p == Platform.FACEBOOK]
    chips = [{"key": "all", "label": "All", "count": row.current_count}] + [
        {"key": p, "label": dict(Platform.choices)[p], "count": row.platform_counts.get(p, 0)} for p in chip_platforms
    ]
    breakdown = []
    authors = {}
    for item in Item.objects.filter(topics=topic, origin__isnull=True).annotate(observed=Coalesce("published_at", "collected_at")).filter(observed__gte=cur_start, observed__lt=cur_end).select_related("source"):
        authors.setdefault(item.source.platform, set()).add(item.author)
    tips = coverage.latest_tip_count(topic, cur_start, cur_end)
    for p in BREAKDOWN_ORDER:
        state = states.get(p)
        if state is None:
            continue
        count = row.platform_counts.get(p, 0)
        status = state["status"]
        if p == Platform.WHATSAPP:
            breakdown.append({"label": "WhatsApp", "value": f"{tips} tip{'s' if tips != 1 else ''}", "count": 0, "status": status,
                              "detail": "Tips are not counted in trends"})
            continue
        if status == "awaiting":
            value, detail = "—", "Not collected · " + (state["source"].note or "awaiting access").rstrip(".").lower() if state["source"].note else "Not collected"
        elif status == "manual" and count == 0:
            value, detail = "—", "No links submitted this hour"
        else:
            value = str(count)
            n = len(authors.get(p, ()))
            who = {"news": "outlet", "youtube": "channel", "facebook": "page"}.get(p, "account")
            prefix = f"{n} {who}{'s' if n != 1 else ''} · " if n else ""
            detail = prefix + state["check"].replace(" · delayed", "").replace("Last successful check", "last check").replace("Checked at", "checked")
        breakdown.append({"label": dict(Platform.choices)[p], "value": value, "count": count, "status": status, "detail": detail,
                          "status_label": coverage.STATUS_LABELS[status]})
    scale = max(max(row.buckets), 3) + 1  # one unit of headroom for value labels
    bucket_times = [hm(w["previous"][0] + timedelta(minutes=10 * i)) for i in range(len(row.buckets) + 1)]
    bars = [{"value": v, "pct": round(100 * v / scale), "current": i >= len(row.buckets) // 2,
             "label": f"{bucket_times[i]}–{bucket_times[i + 1]}"} for i, v in enumerate(row.buckets)]
    first_items = items[:3] if platform == "all" else []
    biggest = max(items, key=lambda i: i.copy_count, default=None)
    topic_options = calc.rows.select_related("topic").filter(rank__isnull=False).order_by("rank")
    if subject != "all":
        topic_options = topic_options.filter(Q(topic__subject=subject) | Q(topic=topic))
    ctx = {
        "calc": calc, "row": row, "topic": topic, "windows": _windows(calc), "items": shown, "item_total": len(items),
        "show_all": show_all, "platform": platform, "subject": subject, "chips": chips, "breakdown": breakdown, "bars": bars,
        "axis": bucket_times[::2], "ticks": list(range(scale, -1, -1)), "grid_step": round(160 / scale, 2),
        "first_items": first_items, "biggest": biggest if biggest and biggest.copy_count else None,
        "topic_options": topic_options, "subject_filters": SUBJECT_FILTERS,
        "linked_cases": _decorate_cases(topic.cases.exclude(status=Case.Status.CLOSED).select_related("owner", "decision_by"), clock.now()),
        "platform_names": [dict(Platform.choices)[p] for p in row.platforms],
        "partial_names": [dict(Platform.choices)[p] for p in row.partial_platforms],
        "nav": "trends",
    }
    return render(request, "desk/trend_detail.html", ctx)


@login_required
def issue_list(request):
    now = clock.now()
    open_cases = queue_context(now)["cases"]
    closed = _decorate_cases(Case.objects.filter(status=Case.Status.CLOSED).select_related("owner", "decision_by").order_by("-closed_at"), now)
    return render(request, "desk/issue_list.html", {"open_cases": open_cases, "closed_cases": closed, "nav": "issues"})


def _case_or_404(ref):
    return get_object_or_404(Case.objects.select_related("owner", "topic", "origin_item__source", "finding_by", "decision_by"), ref=ref)


@login_required
def issue_detail(request, ref):
    case = _case_or_404(ref)
    now = clock.now()
    user = request.user
    is_editor = user.has_perm("desk.decide_case")
    item = case.origin_item
    attached = case.evidence.exclude(document__isnull=True).values_list("document", flat=True)
    ctx = {
        "case": case, "item": item, "copy_count": item.copies.count() if item else 0, "due": _due(case, now),
        "evidence": case.evidence.select_related("added_by"), "events": case.events.select_related("actor"),
        "documents": Document.objects.exclude(pk__in=attached), "findings": [(f.value, f.label) for f in Case.FINDINGS],
        "is_owner": case.owner_id == user.pk, "can_take": case.is_open and not case.owner_id,
        "can_work": workflow.can_work(case, user), "is_editor": is_editor,
        "decisions": workflow.available_decisions(case) if is_editor else set(),
        "nav": "issues",
    }
    return render(request, "desk/issue_detail.html", ctx)


def _back(case, anchor=""):
    return redirect(reverse("desk:issue_detail", args=[case.ref]) + anchor)


def _run(request, case, fn, *args, ok=None, **kwargs):
    try:
        fn(*args, **kwargs)
    except workflow.WorkflowError as exc:
        messages.error(request, str(exc))
        return False
    if ok:
        messages.success(request, ok)
    return True


@login_required
@require_POST
def issue_take(request, ref):
    case = _case_or_404(ref)
    _run(request, case, workflow.take_ownership, case, request.user)
    return _back(case)


@login_required
@require_POST
def issue_release(request, ref):
    case = _case_or_404(ref)
    _run(request, case, workflow.release_ownership, case, request.user, ok="Ownership released.")
    return _back(case)


@login_required
@require_POST
def issue_evidence(request, ref):
    case = _case_or_404(ref)
    doc = Document.objects.filter(pk=request.POST.get("document") or 0).first()
    stance = request.POST.get("stance", Evidence.Stance.PRIMARY)
    if stance not in Evidence.Stance.values:
        stance = Evidence.Stance.PRIMARY
    if doc:
        _run(request, case, workflow.add_evidence, case, request.user, document=doc, stance=stance, ok="Evidence added.")
    elif request.POST.get("url") and request.POST.get("title"):
        _run(request, case, workflow.add_evidence, case, request.user, title=request.POST["title"], url=request.POST["url"],
             key_line=request.POST.get("key_line", ""), stance=stance, ok="Evidence added.")
    else:
        messages.error(request, "Choose a document or enter a title and link.")
    return _back(case, "#evidence")


@login_required
@require_POST
def issue_translation(request, ref):
    case = _case_or_404(ref)
    _run(request, case, workflow.review_translation, case, request.user, request.POST.get("translation", ""), ok="Translation marked as reviewed.")
    return _back(case, "#original")


@login_required
@require_POST
def issue_finding(request, ref):
    case = _case_or_404(ref)
    cited = [int(x) for x in request.POST.getlist("cite") if x.isdigit()]
    done = _run(request, case, workflow.submit_finding, case, request.user, request.POST.get("finding", ""),
                request.POST.get("rationale", ""), cited, ok="Finding submitted for editor review.")
    return _back(case, "" if done else "#finding")


@login_required
@require_POST
def issue_decision(request, ref):
    case = _case_or_404(ref)
    action = request.POST.get("action", "")
    if not request.user.has_perm("desk.decide_case"):
        raise PermissionDenied("Only a duty editor can decide a case.")
    labels = {"escalate": "Escalated to Critical · L4.", "close": "Case closed.",
              "reopen": "Case reopened.", "send_back": "Finding sent back to the analyst."}
    base_url = request.build_absolute_uri("/")[:-1]
    done = _run(request, case, workflow.decide, case, request.user, action, request.POST.get("note", ""),
                request.POST.get("next_action", ""), base_url=base_url, ok=labels.get(action))
    if done and action == "escalate":
        notif = case.notifications.filter(dedupe_key=f"{case.ref}:l4").first()
        if notif:
            if notif.status == "sent":
                messages.info(request, "Telegram alert dispatched to War Room.")
            elif notif.status == "failed":
                messages.warning(request, f"Telegram alert delivery failed: {notif.error_message}")
    if done and action == "approve":
        messages.success(request, f"{case.ref} saved: owner {workflow.display_name(case.owner) if case.owner else 'none'}, finding “{case.get_verification_display()}” approved.")
        return redirect("desk:overview")
    return _back(case)


@login_required
@require_POST
def issue_retry_notification(request, ref):
    case = _case_or_404(ref)
    if not request.user.has_perm("desk.decide_case"):
        raise PermissionDenied("Only a duty editor can retry an alert.")
    from . import notifications
    base_url = request.build_absolute_uri("/")[:-1]
    notif = notifications.dispatch_case_alert(case, base_url=base_url, force_retry=True)
    if notif:
        if notif.status == "sent":
            messages.success(request, "Telegram alert dispatched successfully.")
        elif notif.status == "failed":
            messages.warning(request, f"Telegram alert delivery failed: {notif.error_message}")
        elif notif.status == "disabled":
            messages.warning(request, notif.error_message)
    return _back(case)


@login_required
@require_POST
def issue_new(request):
    item = get_object_or_404(Item, pk=request.POST.get("item") or 0)
    case, _ = workflow.open_case_from_item(item, request.user)
    return redirect("desk:issue_detail", case.ref)


@login_required
def sources(request):
    calc = _calc_or_404()
    return render(request, "desk/sources.html", {**coverage.coverage(calc.as_of), "calc": calc, "nav": "sources"})


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    results = {"topics": [], "cases": [], "items": []}
    if q:
        from django.db import connection
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchVector, TrigramSimilarity
            results["topics"] = list(Topic.objects.annotate(similarity=TrigramSimilarity("name", q))
                                     .filter(Q(name__icontains=q) | Q(area__icontains=q) | Q(keywords__icontains=q) | Q(similarity__gt=0.2))
                                     .order_by("-similarity")[:10])
            results["cases"] = list(Case.objects.annotate(similarity=TrigramSimilarity("claim", q),
                                                          search=SearchVector("claim", config="english"))
                                    .filter(Q(ref__icontains=q) | Q(search=q) | Q(similarity__gt=0.15))
                                    .order_by("-similarity")[:10])
            results["items"] = list(Item.objects.filter(origin__isnull=True)
                                    .annotate(similarity=TrigramSimilarity("excerpt", q),
                                              search=SearchVector("title", "excerpt", "summary", "translation", config="english"))
                                    .filter(Q(author__icontains=q) | Q(search=q) | Q(similarity__gt=0.15) | Q(translation__icontains=q))
                                    .select_related("source")
                                    .order_by("-similarity", "-collected_at")[:20])
        else:
            results["topics"] = list(Topic.objects.filter(Q(name__icontains=q) | Q(area__icontains=q))[:10])
            results["cases"] = list(Case.objects.filter(Q(claim__icontains=q) | Q(ref__icontains=q))[:10])
            results["items"] = list(Item.objects.filter(origin__isnull=True).filter(
                Q(excerpt__icontains=q) | Q(author__icontains=q) | Q(translation__icontains=q)).select_related("source")[:20])
    return render(request, "desk/search.html", {"q": q, **results})


@require_POST
def sample_role(request):
    if not settings.DESK_SAMPLE_MODE:
        raise Http404()
    user = get_object_or_404(sample_people(), username=request.POST.get("username", ""))
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse("desk:overview")
    return redirect(target)
