"""Sign-in lockout and audit log (desk/signin.py)."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from desk.models import SignInEvent
from desk.signin import client_ip

PASSWORD = "a-long-test-password-9"


@override_settings(DESK_SIGNIN_MAX_FAILURES=5, DESK_SIGNIN_MAX_FAILURES_PER_IP=20, DESK_SIGNIN_LOCK_MINUTES=15,
                   DESK_TRUST_PROXY_HEADERS=False, DESK_SAMPLE_MODE=False)
class LockoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("ama.editor", password=PASSWORD)

    def attempt(self, password, username="ama.editor", ip="203.0.113.7"):
        return self.client.post(reverse("login"), {"username": username, "password": password}, REMOTE_ADDR=ip)

    def outcomes(self):
        return list(SignInEvent.objects.order_by("at", "id").values_list("outcome", flat=True))

    def test_successful_sign_in_is_recorded(self):
        response = self.attempt(PASSWORD)
        self.assertEqual(response.status_code, 302)
        event = SignInEvent.objects.get()
        self.assertEqual((event.outcome, event.user, event.ip), ("success", self.user, "203.0.113.7"))

    def test_five_failures_lock_the_account_even_for_the_right_password(self):
        for _ in range(5):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        response = self.attempt(PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed sign-in attempts")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.outcomes(), ["failure"] * 5 + ["locked"])

    def test_wrong_password_shows_the_usual_message(self):
        self.assertContains(self.attempt("wrong"), "The username or password is not correct.")

    def test_lock_expires_after_the_window(self):
        for _ in range(5):
            self.attempt("wrong")
        later = timezone.now() + timedelta(minutes=16)
        with mock.patch("desk.signin.timezone.now", return_value=later):
            self.assertEqual(self.attempt(PASSWORD).status_code, 302)

    def test_success_resets_the_count(self):
        for _ in range(4):
            self.attempt("wrong")
        self.assertEqual(self.attempt(PASSWORD).status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.attempt("wrong")
        self.assertEqual(self.attempt(PASSWORD).status_code, 302)

    def test_username_case_does_not_dodge_the_lock(self):
        for name in ("ama.editor", "AMA.EDITOR", "Ama.Editor", "ama.EDITOR", "aMa.editor"):
            self.attempt("wrong", username=name)
        self.assertContains(self.attempt(PASSWORD), "Too many failed sign-in attempts")

    def test_one_address_guessing_many_usernames_is_locked(self):
        for i in range(20):
            self.attempt("wrong", username=f"guess{i}", ip="198.51.100.9")
        self.assertContains(self.attempt(PASSWORD, ip="198.51.100.9"), "Too many failed sign-in attempts")
        self.assertEqual(self.attempt(PASSWORD, ip="203.0.113.7").status_code, 302)  # other addresses unaffected

    def test_admin_sign_in_uses_the_same_lock(self):
        for _ in range(5):
            self.attempt("wrong")
        response = self.client.post(reverse("admin:login"), {"username": "ama.editor", "password": PASSWORD},
                                    REMOTE_ADDR="203.0.113.7")
        self.assertContains(response, "Too many failed sign-in attempts")

    def test_sign_out_is_recorded(self):
        self.attempt(PASSWORD)
        self.client.post(reverse("logout"))
        self.assertEqual(self.outcomes(), ["success", "sign_out"])


class ClientIpTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="203.0.113.5",
                                            HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1")

    @override_settings(DESK_TRUST_PROXY_HEADERS=False)
    def test_proxy_headers_are_ignored_unless_trusted(self):
        self.assertEqual(client_ip(self.request), "10.0.0.1")

    @override_settings(DESK_TRUST_PROXY_HEADERS=True)
    def test_behind_nginx_the_real_address_is_used(self):
        self.assertEqual(client_ip(self.request), "203.0.113.5")

    @override_settings(DESK_TRUST_PROXY_HEADERS=False)
    def test_garbage_is_not_stored(self):
        self.assertIsNone(client_ip(RequestFactory().get("/", REMOTE_ADDR="not-an-ip")))
