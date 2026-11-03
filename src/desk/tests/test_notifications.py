import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from desk import clock, notifications, workflow
from desk.ingest import replay
from desk.models import Case, CaseNotification, Document, Evidence


class NotificationUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)
        User = get_user_model()
        cls.ama = User.objects.get(username="ama")  # Duty editor
        cls.kwame = User.objects.get(username="kwame")  # Analyst

    def test_format_critical_alert_contains_required_fields_and_links(self):
        case = Case.objects.get(ref="ISS-0412")
        case.urgency = Case.Urgency.CRITICAL
        case.urgency_reason = "National grid collapse risk confirmed."
        case.save()

        doc = Document.objects.get(key="sample-tariff-notice-2026-10-28")
        Evidence.objects.create(
            case=case,
            document=doc,
            title=doc.title,
            publisher=doc.publisher,
            url="https://example.com/official-tariff-notice.pdf",
            dated=doc.dated,
            stance=Evidence.Stance.PRIMARY,
            cited=True,
            added_by=self.kwame,
            added_at=clock.now(),
        )

        text = notifications.format_critical_alert(case, base_url="https://desk.npp.org.gh")

        self.assertIn("CRITICAL · L4 ESCALATION", text)
        self.assertIn("ISS-0412", text)
        self.assertIn("National grid collapse risk confirmed.", text)
        self.assertIn("https://desk.npp.org.gh/issues/ISS-0412/", text)
        self.assertIn("https://example.com/official-tariff-notice.pdf", text)
        self.assertIn("Primary evidence", text)

    @patch("desk.notifications.urllib.request.urlopen")
    def test_escalation_triggers_telegram_dispatch(self, mock_urlopen):
        # Mock successful Telegram response
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 12345}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        case = Case.objects.get(ref="ISS-0412")
        self.assertNotEqual(case.urgency, Case.Urgency.CRITICAL)

        env = {
            "TELEGRAM_BOT_TOKEN": "test_bot_token_xyz",
            "TELEGRAM_CHAT_ID": "-10099887766",
            "DESK_BASE_URL": "http://127.0.0.1:8000",
        }
        with patch.dict(os.environ, env):
            workflow.decide(case, self.ama, "escalate", note="Confirmed tariff panic on radio.")

        case.refresh_from_db()
        self.assertEqual(case.urgency, Case.Urgency.CRITICAL)
        self.assertEqual(case.decision, Case.Decision.ESCALATED)

        notif = CaseNotification.objects.get(case=case)
        self.assertEqual(notif.status, CaseNotification.Status.SENT)
        self.assertEqual(notif.external_message_id, "12345")
        self.assertEqual(notif.recipient, "-10099887766")
        self.assertEqual(notif.dedupe_key, "ISS-0412:l4")
        self.assertIsNotNone(notif.sent_at)

        # Check HTTP request payload
        self.assertEqual(mock_urlopen.call_count, 1)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.telegram.org/bottest_bot_token_xyz/sendMessage")
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["chat_id"], "-10099887766")
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertIn("ISS-0412", payload["text"])

    @patch("desk.notifications.urllib.request.urlopen")
    def test_deduplication_prevents_second_alert(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 54321}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        case = Case.objects.get(ref="ISS-0412")
        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat123"}
        with patch.dict(os.environ, env):
            workflow.decide(case, self.ama, "escalate", note="Reason 1")
            self.assertEqual(mock_urlopen.call_count, 1)

            # Attempt a duplicate dispatch for the same case
            second_notif = notifications.dispatch_case_alert(case)
            self.assertEqual(mock_urlopen.call_count, 1)  # No second HTTP call made
            self.assertEqual(CaseNotification.objects.filter(case=case).count(), 1)
            self.assertEqual(second_notif.status, CaseNotification.Status.SENT)

    @patch("desk.notifications.urllib.request.urlopen")
    def test_dispatch_failure_does_not_block_case_escalation(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        case = Case.objects.get(ref="ISS-0412")
        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat123"}
        with patch.dict(os.environ, env):
            # Workflow must succeed even though Telegram failed
            workflow.decide(case, self.ama, "escalate", note="Confirmed national issue.")

        case.refresh_from_db()
        self.assertEqual(case.urgency, Case.Urgency.CRITICAL)
        self.assertEqual(case.decision, Case.Decision.ESCALATED)

        notif = CaseNotification.objects.get(case=case)
        self.assertEqual(notif.status, CaseNotification.Status.FAILED)
        self.assertIn("Connection timed out", notif.error_message)

    def test_missing_credentials_marks_status_disabled(self):
        case = Case.objects.get(ref="ISS-0412")
        env = {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
        with patch.dict(os.environ, env, clear=True):
            workflow.decide(case, self.ama, "escalate", note="No bot creds in env.")

        case.refresh_from_db()
        self.assertEqual(case.urgency, Case.Urgency.CRITICAL)

        notif = CaseNotification.objects.get(case=case)
        self.assertEqual(notif.status, CaseNotification.Status.DISABLED)
        self.assertIn("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing", notif.error_message)

    @patch("desk.notifications.urllib.request.urlopen")
    def test_editor_can_retry_failed_notification(self, mock_urlopen):
        # Create a failed notification
        case = Case.objects.get(ref="ISS-0412")
        case.urgency = Case.Urgency.CRITICAL
        case.urgency_reason = "Critical"
        case.save()

        notif = CaseNotification.objects.create(
            case=case,
            channel=CaseNotification.Channel.TELEGRAM,
            urgency=case.urgency,
            recipient="chat123",
            dedupe_key=f"{case.ref}:l4",
            status=CaseNotification.Status.FAILED,
            message_text="Initial text",
            error_message="HTTP 500: Server error",
            created_at=clock.now(),
        )

        # Non-editor cannot retry
        self.client.force_login(self.kwame)
        resp = self.client.post(reverse("desk:issue_retry_notification", args=[case.ref]))
        self.assertEqual(resp.status_code, 403)

        # Editor retries successfully
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 889900}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        self.client.force_login(self.ama)
        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat123"}
        with patch.dict(os.environ, env):
            resp = self.client.post(reverse("desk:issue_retry_notification", args=[case.ref]))
            self.assertRedirects(resp, reverse("desk:issue_detail", args=[case.ref]))

        notif.refresh_from_db()
        self.assertEqual(notif.status, CaseNotification.Status.SENT)
        self.assertEqual(notif.external_message_id, "889900")
        self.assertEqual(notif.error_message, "")

