"""Phase 0 guards: the passwordless demo sign-in can only open fictional sample people,
and sample mode can never be switched on for a live deployment."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from desk.ingest import ensure_groups, sample_people
from desk_site.safety import sample_mode

LOCAL = {"debug": True, "database_url": "", "allowed_hosts": ["localhost", "127.0.0.1", "[::1]"]}


class SampleModeSettingTests(SimpleTestCase):
    def test_plain_local_demo_defaults_on(self):
        self.assertTrue(sample_mode(None, **LOCAL))

    def test_live_looking_settings_default_off(self):
        self.assertFalse(sample_mode(None, **{**LOCAL, "debug": False}))
        self.assertFalse(sample_mode(None, **{**LOCAL, "database_url": "postgresql://u:p@db/desk"}))
        self.assertFalse(sample_mode(None, **{**LOCAL, "allowed_hosts": ["desk.example.org"]}))

    def test_explicit_sample_mode_on_a_live_deployment_refuses_to_start(self):
        for live in ({"debug": False}, {"database_url": "postgresql://u:p@db/desk"}, {"allowed_hosts": ["desk.example.org"]}):
            with self.subTest(live=live), self.assertRaises(ImproperlyConfigured):
                sample_mode("1", **{**LOCAL, **live})

    def test_explicit_values_on_a_laptop(self):
        self.assertTrue(sample_mode("1", **LOCAL))
        self.assertFalse(sample_mode("0", **LOCAL))


@override_settings(DESK_SAMPLE_MODE=True)
class SampleSignInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        editors = ensure_groups()
        User = get_user_model()
        # A fictional sample person, exactly as replay_sample creates them.
        cls.sample = User.objects.create(username="ama", first_name="Ama", last_name="Owusu")
        cls.sample.set_unusable_password()
        cls.sample.save()
        cls.sample.groups.add(editors)
        # A real duty editor with a password.
        cls.real = User.objects.create_user("real.editor", password="a-long-test-password-1")
        cls.real.groups.add(editors)
        # A real account that reuses a sample username: still never openable without its password.
        cls.lookalike = User.objects.create_user("kwame", password="a-long-test-password-2")
        cls.lookalike.groups.add(Group.objects.get(name="Analyst"))

    def sign_in_as(self, username):
        return self.client.post(reverse("desk:sample_role"), {"username": username})

    def test_only_fictional_sample_people_qualify(self):
        self.assertEqual(list(sample_people().values_list("username", flat=True)), ["ama"])

    def test_sample_person_signs_in(self):
        self.assertRedirects(self.sign_in_as("ama"), reverse("desk:overview"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.sample.pk)

    def test_real_staff_cannot_be_opened_without_a_password(self):
        for username in ("real.editor", "kwame", "nobody"):
            with self.subTest(username=username):
                self.assertEqual(self.sign_in_as(username).status_code, 404)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_sign_in_page_lists_only_sample_people(self):
        page = self.client.get(reverse("login")).content.decode()
        self.assertIn('value="ama"', page)
        self.assertNotIn('value="real.editor"', page)
        self.assertNotIn('value="kwame"', page)

    @override_settings(DESK_SAMPLE_MODE=False)
    def test_switch_is_off_outside_sample_mode(self):
        self.assertEqual(self.sign_in_as("ama").status_code, 404)
