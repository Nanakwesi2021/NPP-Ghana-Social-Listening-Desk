"""/healthz/ for uptime monitors.

Public, no sign-in, and deliberately uninformative: it reports only whether the database
answers and, on a live desk, whether trends were recalculated and sources polled recently.
A stopped worker shows up as stale trends or stale collection and returns 503, so the
monitor alerts even though the website itself still loads.
"""
from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import PollRun, TrendCalculation


def _age_check(latest, limit_minutes, now):
    if latest is None:
        return "none", None
    minutes = int((now - latest).total_seconds() // 60)
    return ("ok" if minutes <= limit_minutes else "stale"), minutes


@never_cache
@require_GET
def healthz(request):
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except DatabaseError:
        return JsonResponse({"status": "down", "checks": {"database": "down"}}, status=503)

    if not settings.DESK_SAMPLE_MODE:
        now = timezone.now()
        latest_calc = TrendCalculation.objects.order_by("-computed_at").values_list("computed_at", flat=True).first()
        latest_poll = PollRun.objects.order_by("-finished_at").values_list("finished_at", flat=True).first()
        checks["trends"], trends_age = _age_check(latest_calc, settings.DESK_HEALTH_MAX_TREND_AGE_MINUTES, now)
        checks["collection"], poll_age = _age_check(latest_poll, settings.DESK_HEALTH_MAX_POLL_AGE_MINUTES, now)
        checks["trends_age_minutes"], checks["collection_age_minutes"] = trends_age, poll_age
    healthy = all(v == "ok" for k, v in checks.items() if not k.endswith("_minutes"))
    return JsonResponse({"status": "ok" if healthy else "degraded", "checks": checks}, status=200 if healthy else 503)
