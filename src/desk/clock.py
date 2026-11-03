"""Desk time.

In sample mode the shift clock starts at the fixture's shift time and advances at real speed,
so actions taken during a demo get plausible GMT times. Trend windows never use this clock
directly: they use the time of the calculation they were computed for.
"""
from django.conf import settings
from django.utils import timezone


def now():
    if settings.DESK_SAMPLE_MODE:
        from .models import ShiftClock

        clock = ShiftClock.objects.first()
        if clock:
            return clock.sample_start + (timezone.now() - clock.real_start)
    return timezone.now()
