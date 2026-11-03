"""Two-step sign-in: a password, then a six-digit code from an authenticator app.

1. The usual sign-in form checks the password, with the lockout in signin.py.
2. TwoStepMiddleware sends a person who has signed in but not yet entered a code to the
   code page. If their account has no authenticator app yet and two-step is required, it
   sends them to the set-up page instead.
3. The code page accepts a code from the app, or one of ten single-use backup codes.
   django-otp refuses a code that has already been used and makes each wrong code wait
   twice as long as the last (1, 2, 4, 8 … seconds) before the next try is checked.

Two-step is required for every account when sample mode is off (DESK_TWO_STEP_REQUIRED),
which is always the case on a live deployment. An account that has set it up is asked
for a code everywhere, even where it is not required.

A password alone is never enough to add a phone to an account that already has one: the
set-up page is open without a code only while the account has no authenticator app. That
leaves one gap, between an administrator creating an account and its owner setting up
their phone, so people should set up at their first sign-in. `provision_user --list`
shows who has not. To replace a lost phone, an administrator runs
`provision_user --username NAME --reset-two-step`, and the person sets up again at their
next sign-in.
"""
from base64 import b32encode
from urllib.parse import urlencode

import django_otp
import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django_otp import user_has_device
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import SignInEvent
from .signin import record_event

# Pages a signed-in person can open before entering a code.
EXEMPT_VIEWS = frozenset({
    "login", "logout", "healthz", "two_step_verify", "two_step_setup", "admin:logout",
    "desk:sample_role",  # 404 outside sample mode; switching sample person signs in afresh
})
NEW_CODES_SESSION_KEY = "desk_two_step_new_codes"
APP_DEVICE_NAME = "Authenticator app"
BACKUP_DEVICE_NAME = "Backup codes"
WRONG_CODE = ("That code is not right. Use the newest code in the app, and check that the phone sets "
              "its time automatically.")


def _next_url(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return reverse("desk:overview")


def _to(name, next_url):
    return f"{reverse(name)}?{urlencode({'next': next_url})}"


def _locked_message(locked_until):
    return f"Too many wrong codes. Try again after {timezone.localtime(locked_until):%H:%M:%S} GMT."


def _code_from(request):
    """The typed code without spaces or hyphens, lower case (backup codes are stored that way)."""
    return "".join((request.POST.get("code") or "").split()).replace("-", "").lower()[:16]


def _is_app_code(code):
    return len(code) == 6 and code.isdigit()


class TwoStepMiddleware:
    """Keep a signed-in person on the code or set-up page until they have entered a code."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_verified():
            return None
        if request.resolver_match and request.resolver_match.view_name in EXEMPT_VIEWS:
            return None
        if user_has_device(user):
            target = "two_step_verify"
        elif settings.DESK_TWO_STEP_REQUIRED:
            target = "two_step_setup"
        else:
            return None
        # Only come back to pages that can be opened again; a form post goes to the desk instead.
        next_url = request.get_full_path() if request.method == "GET" else reverse("desk:overview")
        return redirect(_to(target, next_url))


def check_code(user, code):
    """Check a code against the account's authenticator app or its backup codes.

    Returns (device, locked_until). A six-digit code is checked against the app and anything
    else against the backup codes, so each keeps its own count of wrong tries.
    """
    if not code:
        return None, None
    model = TOTPDevice if _is_app_code(code) else StaticDevice
    locked_until = None
    for device in model.objects.devices_for_user(user, confirmed=True):
        allowed, info = device.verify_is_allowed()
        if not allowed:
            locked_until = (info or {}).get("locked_until")
            continue
        verified = django_otp.verify_token(user, device.persistent_id, code)
        if verified is not None:
            return verified, None
    return None, locked_until


def new_backup_codes(user):
    """Replace the account's backup codes with fresh ones and return them, to show once."""
    with transaction.atomic():
        device = StaticDevice.objects.filter(user=user).order_by("id").first()
        if device is None:
            device = StaticDevice.objects.create(user=user, name=BACKUP_DEVICE_NAME)
        StaticDevice.objects.filter(user=user).exclude(pk=device.pk).delete()
        device.token_set.all().delete()
        codes = [StaticToken.random_token() for _ in range(settings.DESK_TWO_STEP_BACKUP_CODES)]
        StaticToken.objects.bulk_create([StaticToken(device=device, token=code) for code in codes])
    return codes


def reset_two_step(user):
    """Remove the account's authenticator app and backup codes. Returns True if it had any."""
    with transaction.atomic():
        had_any = user_has_device(user, confirmed=None)
        TOTPDevice.objects.filter(user=user).delete()
        StaticDevice.objects.filter(user=user).delete()
        record_event(None, SignInEvent.Outcome.CODE_RESET, user=user)
    return had_any


def has_authenticator(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def _qr_svg(device):
    qr = segno.make(device.config_url, error="m")
    return mark_safe(qr.svg_inline(scale=4, border=2, dark="#000000", light="#ffffff",
                                   title="QR code to add the desk to your authenticator app"))


def _key_for_typing(device):
    key = b32encode(device.bin_key).decode()
    return " ".join(key[i:i + 4] for i in range(0, len(key), 4))


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def verify(request):
    user, next_url = request.user, _next_url(request)
    if user.is_verified():
        return redirect(next_url)
    if not user_has_device(user):
        return redirect(_to("two_step_setup", next_url))

    error = ""
    if request.method == "POST":
        device, locked_until = check_code(user, _code_from(request))
        if device is not None:
            django_otp.login(request, device)
            record_event(request, SignInEvent.Outcome.CODE_OK, user=user)
            if isinstance(device, StaticDevice):
                left = device.token_set.count()
                messages.warning(request, f"You used a backup code. {left} left. To make new ones, open "
                                          "Two-step sign-in in your account menu.")
            return redirect(next_url)
        record_event(request, SignInEvent.Outcome.CODE_WRONG, user=user)
        error = _locked_message(locked_until) if locked_until else WRONG_CODE
    return render(request, "registration/two_step_verify.html",
                  {"error": error, "next": next_url, "issuer": settings.OTP_TOTP_ISSUER,
                   "backup": request.GET.get("backup") == "1"})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def setup(request):
    user, next_url = request.user, _next_url(request)
    replacing = user_has_device(user)
    if replacing and not user.is_verified():
        return redirect(_to("two_step_verify", next_url))
    if not user.has_usable_password():
        return redirect(next_url)  # sample people sign in without a password and cannot set this up

    device = (TOTPDevice.objects.filter(user=user, confirmed=False).order_by("-id").first()
              or TOTPDevice.objects.create(user=user, name=APP_DEVICE_NAME, confirmed=False))
    error = ""
    if request.method == "POST":
        code = _code_from(request)
        allowed, info = device.verify_is_allowed()
        if not allowed:
            error = _locked_message(info["locked_until"])
        else:
            confirmed = django_otp.verify_token(user, device.persistent_id, code) if _is_app_code(code) else None
            if confirmed is not None:
                with transaction.atomic():
                    TOTPDevice.objects.filter(user=user).exclude(pk=confirmed.pk).delete()
                    confirmed.confirmed = True
                    confirmed.save(update_fields=["confirmed"])
                    codes = new_backup_codes(user)
                django_otp.login(request, confirmed)
                record_event(request, SignInEvent.Outcome.CODE_SETUP, user=user)
                request.session[NEW_CODES_SESSION_KEY] = {"codes": codes, "reason": "setup"}
                return redirect(_to("two_step_settings", next_url))
            if not _is_app_code(code):
                device.throttle_increment()
            error = WRONG_CODE
    return render(request, "registration/two_step_setup.html", {
        "error": error, "next": next_url, "replacing": replacing, "qr_svg": _qr_svg(device),
        "key": _key_for_typing(device), "issuer": settings.OTP_TOTP_ISSUER,
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def manage(request):
    user, next_url = request.user, _next_url(request)
    if not user.is_verified():
        return redirect(_to("two_step_verify" if user_has_device(user) else "two_step_setup", next_url))
    if request.method == "POST":
        request.session[NEW_CODES_SESSION_KEY] = {"codes": new_backup_codes(user), "reason": "new"}
        return redirect(_to("two_step_settings", next_url))

    new = request.session.pop(NEW_CODES_SESSION_KEY, None) or {}
    return render(request, "registration/two_step_settings.html", {
        "next": next_url,
        "new_codes": [f"{c[:4]} {c[4:]}".upper() for c in new.get("codes", [])],  # typed in any case
        "just_set_up": new.get("reason") == "setup",
        "codes_left": StaticToken.objects.filter(device__user=user, device__confirmed=True).count(),
        "app": TOTPDevice.objects.filter(user=user, confirmed=True).first(),
    })
