"""Sign-in protection: a lockout after repeated failures, and an audit log of every attempt.

A username is refused for DESK_SIGNIN_LOCK_MINUTES after DESK_SIGNIN_MAX_FAILURES failed
attempts since its last successful sign-in. An address is refused after
DESK_SIGNIN_MAX_FAILURES_PER_IP failures, which stops one machine guessing across many
usernames. Refusals do not reveal whether the username exists.

Behind Nginx the visitor's address arrives in X-Real-IP. That header is only trusted when
DESK_TRUST_PROXY_HEADERS is on, because anyone can send it to a server that is reachable
directly.
"""
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.utils import timezone

from .models import SignInEvent

LOCKED_MESSAGE = "Too many failed sign-in attempts. Wait {minutes} minutes, or ask an administrator to check the account."


def client_ip(request):
    if request is None:
        return None
    if settings.DESK_TRUST_PROXY_HEADERS:
        candidate = request.META.get("HTTP_X_REAL_IP") or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
    else:
        candidate = request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def record_event(request, outcome, *, username="", user=None):
    SignInEvent.objects.create(
        at=timezone.now(), outcome=outcome, user=user,
        username=(username or (user.get_username() if user else ""))[:150],
        ip=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:300],
    )


def is_locked(username, ip, now=None):
    now = now or timezone.now()
    since = now - timedelta(minutes=settings.DESK_SIGNIN_LOCK_MINUTES)
    failures = SignInEvent.objects.filter(outcome=SignInEvent.Outcome.FAILURE, at__gte=since)
    if username:
        last_success = (SignInEvent.objects.filter(username__iexact=username, outcome=SignInEvent.Outcome.SUCCESS)
                        .values_list("at", flat=True).first())
        mine = failures.filter(username__iexact=username)
        if last_success:
            mine = mine.filter(at__gt=last_success)
        if mine.count() >= settings.DESK_SIGNIN_MAX_FAILURES:
            return True
    if ip and failures.filter(ip=ip).count() >= settings.DESK_SIGNIN_MAX_FAILURES_PER_IP:
        return True
    return False


class LockoutMixin:
    """Refuse before checking the password, so a locked account cannot be guessed at."""

    locked_message = ""

    def clean(self):
        username = (self.data.get("username") or "").strip()
        if is_locked(username, client_ip(self.request)):
            record_event(self.request, SignInEvent.Outcome.LOCKED, username=username)
            self.locked_message = LOCKED_MESSAGE.format(minutes=settings.DESK_SIGNIN_LOCK_MINUTES)
            raise ValidationError(self.locked_message, code="locked")
        return super().clean()


class LockoutAuthenticationForm(LockoutMixin, AuthenticationForm):
    pass


class LockoutAdminAuthenticationForm(LockoutMixin, AdminAuthenticationForm):
    pass


@receiver(user_logged_in, dispatch_uid="desk_signin_success")
def _on_sign_in(sender, request, user, **kwargs):
    record_event(request, SignInEvent.Outcome.SUCCESS, user=user)


@receiver(user_logged_out, dispatch_uid="desk_signin_sign_out")
def _on_sign_out(sender, request, user, **kwargs):
    if user is not None:
        record_event(request, SignInEvent.Outcome.SIGN_OUT, user=user)


@receiver(user_login_failed, dispatch_uid="desk_signin_failure")
def _on_failure(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get(get_user_model().USERNAME_FIELD, "") or ""
    record_event(request, SignInEvent.Outcome.FAILURE, username=username)
