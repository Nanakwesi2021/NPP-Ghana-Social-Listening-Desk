"""Two-step sign-in (desk/twostep.py): password, then a code from an authenticator app."""
import time
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from desk.models import SignInEvent
from desk.twostep import WRONG_CODE, new_backup_codes

PASSWORD = "a-long-test-password-9"


def code_for(device, when=None):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time() if when is None else when
    return f"{totp.token():06d}"


def wrong(code):
    return f"{(int(code) + 500_000) % 1_000_000:06d}"


@override_settings(DESK_TWO_STEP_REQUIRED=True, DESK_SAMPLE_MODE=False, DESK_TRUST_PROXY_HEADERS=False,
                   OTP_TOTP_THROTTLE_FACTOR=0, OTP_STATIC_THROTTLE_FACTOR=0)
class TwoStepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("ama.editor", password=PASSWORD)

    def sign_in(self, username="ama.editor", url_name="login"):
        response = self.client.post(reverse(url_name), {"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)

    def add_phone(self, user=None):
        return TOTPDevice.objects.create(user=user or self.user, name="Authenticator app", confirmed=True)

    def enter(self, code, next_url="/desk/"):
        return self.client.post(reverse("two_step_verify"), {"code": code, "next": next_url})

    def outcomes(self):
        return list(SignInEvent.objects.order_by("at", "id").values_list("outcome", flat=True))

    def assertRedirectsTo(self, response, url_name, next_url):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse(url_name)}?next={next_url.replace('/', '%2F')}")

    # Setting up

    def test_a_password_alone_leads_to_set_up_not_the_desk(self):
        self.sign_in()
        self.assertRedirectsTo(self.client.get("/desk/"), "two_step_setup", "/desk/")

    def test_set_up_turns_on_two_step_and_shows_backup_codes_once(self):
        self.sign_in()
        page = self.client.get(reverse("two_step_setup"), {"next": "/issues/"})
        self.assertContains(page, "<svg")
        self.assertIn("no-store", page["Cache-Control"])
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        self.assertContains(page, device.config_url.split("secret=")[1][:4])  # the key, for typing in

        refused = self.client.post(reverse("two_step_setup"), {"code": wrong(code_for(device)), "next": "/issues/"})
        self.assertContains(refused, WRONG_CODE)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user, confirmed=True).exists())

        done = self.client.post(reverse("two_step_setup"), {"code": code_for(device), "next": "/issues/"})
        self.assertRedirectsTo(done, "two_step_settings", "/issues/")
        self.assertTrue(TOTPDevice.objects.get(pk=device.pk).confirmed)
        codes = self.client.get(done["Location"])
        self.assertContains(codes, "Two-step sign-in is on")
        self.assertEqual(codes.content.decode().count("<li>"), 10)
        self.assertContains(self.client.get(done["Location"]), "Backup codes left: <strong class=\"tabular\">10</strong>",
                            html=False)
        self.assertEqual(self.client.get("/issues/").status_code, 200)
        self.assertIn(SignInEvent.Outcome.CODE_SETUP, self.outcomes())

    def test_people_without_a_password_cannot_set_up(self):
        sample = get_user_model().objects.create_user("sample.person")  # unusable password, like sample people
        self.client.force_login(sample)
        self.assertEqual(self.client.get(reverse("two_step_setup"))["Location"], reverse("desk:overview"))
        self.assertFalse(TOTPDevice.objects.filter(user=sample).exists())

    # Signing in with a phone

    def test_signing_in_with_a_phone_needs_the_code(self):
        device = self.add_phone()
        self.sign_in()
        self.assertRedirectsTo(self.client.get("/issues/"), "two_step_verify", "/issues/")
        response = self.enter(code_for(device), next_url="/issues/")
        self.assertEqual(response["Location"], "/issues/")
        self.assertEqual(self.client.get("/issues/").status_code, 200)
        self.assertEqual(self.outcomes(), ["success", "code_ok"])

    def test_wrong_code_is_refused_and_recorded(self):
        device = self.add_phone()
        self.sign_in()
        self.assertContains(self.enter(wrong(code_for(device))), WRONG_CODE)
        self.assertEqual(self.client.get("/desk/").status_code, 302)
        self.assertEqual(self.outcomes(), ["success", "code_wrong"])

    @override_settings(OTP_TOTP_THROTTLE_FACTOR=1)
    def test_repeated_wrong_codes_are_slowed_down(self):
        device = self.add_phone()
        self.sign_in()
        for _ in range(3):
            self.enter(wrong(code_for(device)))
        response = self.enter(code_for(device))
        self.assertContains(response, "Too many wrong codes. Try again after")
        self.assertEqual(self.client.get("/desk/").status_code, 302)

    def test_a_used_code_cannot_be_used_again(self):
        device = self.add_phone()
        code = code_for(device)
        self.sign_in()
        self.assertEqual(self.enter(code).status_code, 302)
        self.client.post(reverse("logout"))
        self.sign_in()
        self.assertContains(self.enter(code), WRONG_CODE)

    def test_a_backup_code_works_once(self):
        self.add_phone()
        first, *_ = new_backup_codes(self.user)
        self.sign_in()
        typed = f"{first[:4].upper()} {first[4:].upper()}"  # as printed, in capitals
        response = self.enter(typed, next_url="/issues/")
        self.assertEqual(response["Location"], "/issues/")
        self.assertContains(self.client.get("/issues/"), "You used a backup code. 9 left.")
        self.client.post(reverse("logout"))
        self.sign_in()
        self.assertContains(self.enter(first), WRONG_CODE)

    def test_the_backup_code_page_does_not_force_a_number_keypad(self):
        self.add_phone()
        self.sign_in()
        self.assertContains(self.client.get(reverse("two_step_verify"), {"backup": "1"}), 'inputmode="text"')

    def test_next_cannot_send_people_off_the_desk(self):
        device = self.add_phone()
        self.sign_in()
        self.assertEqual(self.enter(code_for(device), next_url="https://evil.example/")["Location"], "/desk/")

    # What a password alone can and cannot reach

    def test_a_password_alone_cannot_add_a_second_phone(self):
        self.add_phone()
        self.sign_in()
        self.assertRedirectsTo(self.client.get(reverse("two_step_setup")), "two_step_verify", "/desk/")
        self.client.post(reverse("two_step_setup"), {"code": "123456"})
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)
        self.assertRedirectsTo(self.client.post(reverse("two_step_settings")), "two_step_verify", "/desk/")
        self.assertFalse(StaticToken.objects.exists())

    def test_admin_and_password_change_need_the_code(self):
        staff = get_user_model().objects.create_user("admin.person", password=PASSWORD, is_staff=True,
                                                     is_superuser=True)
        self.add_phone(staff)
        self.sign_in("admin.person", url_name="admin:login")
        self.assertEqual(self.client.get("/admin/")["Location"].split("?")[0], reverse("two_step_verify"))
        self.assertEqual(self.client.get(reverse("password_change"))["Location"].split("?")[0],
                         reverse("two_step_verify"))

    def test_sign_out_and_health_check_work_before_the_code(self):
        self.add_phone()
        self.sign_in()
        self.assertNotEqual(self.client.get(reverse("healthz")).status_code, 302)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_form_post_before_the_code_returns_to_the_desk_afterwards(self):
        self.add_phone()
        self.sign_in()
        response = self.client.post("/issues/ISS-1/take/")
        self.assertRedirectsTo(response, "two_step_verify", "/desk/")

    # Managing two-step sign-in

    def verified(self):
        device = self.add_phone()
        self.sign_in()
        self.enter(code_for(device))
        return device

    def test_a_new_phone_replaces_the_old_one(self):
        old = self.verified()
        old_codes = new_backup_codes(self.user)
        page = self.client.get(reverse("two_step_setup"))
        self.assertContains(page, "Set up a new phone")
        new = TOTPDevice.objects.get(user=self.user, confirmed=False)
        later = time.time() + 90  # a later code than the one used to sign in
        with mock.patch("django_otp.plugins.otp_totp.models.time.time", return_value=later):
            self.client.post(reverse("two_step_setup"), {"code": code_for(new, later)})
        self.assertEqual(list(TOTPDevice.objects.filter(user=self.user).values_list("pk", flat=True)), [new.pk])
        self.assertFalse(TOTPDevice.objects.filter(pk=old.pk).exists())
        self.assertFalse(StaticToken.objects.filter(token__in=old_codes).exists())
        self.assertEqual(StaticToken.objects.filter(device__user=self.user).count(), 10)

    def test_making_new_backup_codes_cancels_the_old_ones(self):
        self.verified()
        old_codes = new_backup_codes(self.user)
        response = self.client.post(reverse("two_step_settings"), {"next": "/desk/"})
        page = self.client.get(response["Location"])
        self.assertContains(page, "Your old backup codes no longer work.")
        self.assertFalse(StaticToken.objects.filter(token__in=old_codes).exists())
        self.assertEqual(StaticToken.objects.filter(device__user=self.user).count(), 10)

    def test_administrator_reset_for_a_lost_phone(self):
        self.add_phone()
        new_backup_codes(self.user)
        out = StringIO()
        call_command("provision_user", "--username", "ama.editor", "--reset-two-step", stdout=out)
        self.assertIn("Two-step sign-in reset for 'ama.editor'", out.getvalue())
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(StaticToken.objects.exists())
        self.assertIn(SignInEvent.Outcome.CODE_RESET, self.outcomes())
        self.sign_in()
        self.assertRedirectsTo(self.client.get("/desk/"), "two_step_setup", "/desk/")

    def test_account_list_shows_who_has_not_set_up(self):
        get_user_model().objects.create_user("kwaku.analyst", password=PASSWORD)
        self.add_phone()
        out = StringIO()
        call_command("provision_user", "--list", stdout=out)
        rows = {line.split()[0]: line for line in out.getvalue().splitlines()[2:]}
        self.assertTrue(rows["ama.editor"].rstrip().endswith("On"))
        self.assertTrue(rows["kwaku.analyst"].rstrip().endswith("Not set up"))


@override_settings(DESK_TWO_STEP_REQUIRED=False, DESK_SAMPLE_MODE=False, OTP_TOTP_THROTTLE_FACTOR=0)
class TwoStepNotRequiredTests(TestCase):
    """Where two-step is not required (sample mode), it still applies to anyone who set it up."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("ama.editor", password=PASSWORD)

    def test_no_phone_goes_straight_to_the_desk(self):
        self.client.post(reverse("login"), {"username": "ama.editor", "password": PASSWORD})
        self.assertEqual(self.client.get("/issues/").status_code, 200)  # /desk/ needs a shift loaded

    def test_a_phone_that_was_set_up_is_still_asked_for(self):
        TOTPDevice.objects.create(user=self.user, name="Authenticator app", confirmed=True)
        self.client.post(reverse("login"), {"username": "ama.editor", "password": PASSWORD})
        self.assertEqual(self.client.get("/desk/")["Location"].split("?")[0], reverse("two_step_verify"))
