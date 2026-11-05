"""The name people see: War Room."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

BRAND = '<span class="brand__name">War Room</span>'


class NameTests(TestCase):
    def test_sign_in_page_is_called_war_room(self):
        page = self.client.get(reverse("login"))
        self.assertContains(page, "<title>Sign in · War Room</title>", html=False)
        self.assertContains(page, BRAND, html=False)
        self.assertNotContains(page, "Listening Desk")

    def test_desk_pages_are_called_war_room(self):
        self.client.force_login(get_user_model().objects.create_user("ama.editor"))
        page = self.client.get("/issues/")  # /desk/ needs a shift loaded
        self.assertContains(page, " · War Room</title>", html=False)
        self.assertContains(page, BRAND, html=False)
        self.assertNotContains(page, "Listening Desk")

    def test_authenticator_apps_show_war_room(self):
        user = get_user_model().objects.create_user("ama.editor")
        device = TOTPDevice.objects.create(user=user, name="Authenticator app", confirmed=False)
        self.assertIn("issuer=War%20Room", device.config_url)
