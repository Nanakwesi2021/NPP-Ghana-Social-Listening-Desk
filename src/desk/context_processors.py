from django.conf import settings
from django.contrib.auth import get_user_model

from . import clock
from .models import TrendCalculation
from .workflow import role_label


def desk(request):
    calc = TrendCalculation.objects.only("as_of").first()
    ctx = {
        "sample_mode": settings.DESK_SAMPLE_MODE,
        "desk_now": clock.now(),
        "evidence_as_of": calc.as_of if calc else None,
        "refresh_seconds": settings.DESK_REFRESH_SECONDS,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        ctx["user_role"] = role_label(user)
        ctx["user_initials"] = ((user.first_name[:1] + user.last_name[:1]) or user.get_username()[:2]).upper()
    if settings.DESK_SAMPLE_MODE:
        ctx["sample_people"] = get_user_model().objects.filter(groups__isnull=False).distinct().order_by("-groups__name", "first_name")
    return ctx
