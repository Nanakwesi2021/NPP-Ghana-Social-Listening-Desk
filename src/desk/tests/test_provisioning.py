import io
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from desk.ingest import ANALYST_GROUP, EDITOR_GROUP, ensure_groups


class UserProvisioningTests(TestCase):
    def setUp(self):
        ensure_groups()
        self.User = get_user_model()

    def test_provision_duty_editor(self):
        call_command(
            "provision_user",
            username="kojo.editor",
            name="Kojo Mensah",
            email="kojo@example.com",
            role="editor",
            password="StrongEditorPassword123!",
        )
        user = self.User.objects.get(username="kojo.editor")
        self.assertEqual(user.first_name, "Kojo")
        self.assertEqual(user.last_name, "Mensah")
        self.assertEqual(user.email, "kojo@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.groups.filter(name=EDITOR_GROUP).exists())
        self.assertFalse(user.groups.filter(name=ANALYST_GROUP).exists())
        # Editor has decide_case permission
        self.assertTrue(user.has_perm("desk.decide_case"))

        # Verify password auth
        auth_user = authenticate(username="kojo.editor", password="StrongEditorPassword123!")
        self.assertIsNotNone(auth_user)

    def test_provision_analyst_without_decide_permission(self):
        call_command(
            "provision_user",
            username="akua.analyst",
            name="Akua Ansah",
            email="akua@example.com",
            role="analyst",
            password="StrongAnalystPassword123!",
        )
        user = self.User.objects.get(username="akua.analyst")
        self.assertEqual(user.get_full_name(), "Akua Ansah")
        self.assertTrue(user.groups.filter(name=ANALYST_GROUP).exists())
        self.assertFalse(user.groups.filter(name=EDITOR_GROUP).exists())
        # Analyst must NOT have decide_case permission
        self.assertFalse(user.has_perm("desk.decide_case"))

    def test_provision_admin_role(self):
        call_command(
            "provision_user",
            username="admin.lead",
            role="admin",
            password="StrongAdminPassword123!",
        )
        user = self.User.objects.get(username="admin.lead")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.groups.filter(name=EDITOR_GROUP).exists())

    def test_deactivate_and_reactivate_account(self):
        call_command(
            "provision_user",
            username="ya.switch",
            role="analyst",
            password="TestPassword123!",
        )
        user = self.User.objects.get(username="ya.switch")
        self.assertTrue(user.is_active)

        # Deactivate
        call_command("provision_user", username="ya.switch", deactivate=True)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Reactivate
        call_command("provision_user", username="ya.switch", activate=True)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_random_password_generation(self):
        out = io.StringIO()
        call_command(
            "provision_user",
            username="rand.user",
            role="analyst",
            random_password=True,
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("Generated temporary password for rand.user:", output)
        self.assertTrue(self.User.objects.filter(username="rand.user").exists())

    def test_list_accounts(self):
        self.User.objects.create_user(username="testlist", password="Password123!")
        out = io.StringIO()
        call_command("provision_user", list=True, stdout=out)
        self.assertIn("testlist", out.getvalue())
        self.assertIn("USERNAME", out.getvalue())

    def test_missing_arguments_raise_error(self):
        with self.assertRaises(CommandError):
            call_command("provision_user")  # no username or --list

        with self.assertRaises(CommandError):
            call_command("provision_user", username="nobody")  # no role or action


class PasswordManagementViewsTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="kwame.test",
            password="OriginalPassword123!",
        )
        self.client = Client()

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("password_change"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_authenticated_user_can_view_password_change(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("password_change"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Change password")

    def test_successful_password_change_flow(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("password_change"),
            {
                "old_password": "OriginalPassword123!",
                "new_password1": "NewValidPassword2026!#",
                "new_password2": "NewValidPassword2026!#",
            },
        )
        self.assertRedirects(resp, reverse("password_change_done"))

        # Verify old password fails and new password authenticates
        self.assertIsNone(authenticate(username="kwame.test", password="OriginalPassword123!"))
        auth_user = authenticate(username="kwame.test", password="NewValidPassword2026!#")
        self.assertIsNotNone(auth_user)

        # Done page renders cleanly
        done_resp = self.client.get(reverse("password_change_done"))
        self.assertEqual(done_resp.status_code, 200)
        self.assertContains(done_resp, "Password updated successfully")
