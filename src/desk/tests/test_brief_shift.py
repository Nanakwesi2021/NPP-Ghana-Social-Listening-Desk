import io
import json
import os
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from desk.ingest import replay
from desk.management.commands.brief_shift import format_telegram_brief
from desk.models import Case, TrendCalculation


class ShiftBriefCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)

    def test_brief_shift_terminal_output_renders_trends_and_cases(self):
        out = io.StringIO()
        call_command("brief_shift", stdout=out)
        output = out.getvalue()

        # Check sections
        self.assertIn("NPP SOCIAL LISTENING DESK · SHIFT INTELLIGENCE BRIEF", output)
        self.assertIn("1. TOP RISING TOPICS & MOMENTUM", output)
        self.assertIn("2. CRITICAL ISSUES & QUEUE", output)
        self.assertIn("3. SOURCE COVERAGE & PLATFORM HEALTH", output)

        # Check specific sample shift data
        self.assertIn("#1 Electricity tariff increase", output)
        self.assertIn("[ISS-0409]", output)
        self.assertIn("[ISS-0412]", output)
        self.assertIn("News feeds:", output)

    def test_brief_shift_custom_title(self):
        out = io.StringIO()
        call_command("brief_shift", title="Morning Handover (05:45 GMT)", stdout=out)
        output = out.getvalue()
        self.assertIn("NPP SOCIAL LISTENING DESK · MORNING HANDOVER (05:45 GMT)", output)

    def test_format_telegram_brief_html_structure(self):
        calc = TrendCalculation.objects.latest("as_of")
        open_cases = list(Case.objects.exclude(status=Case.Status.CLOSED).order_by("due_at"))
        cov_rows = [{"name": "News feeds", "label": "Current", "status": "current", "check": "All checked"}]

        html = format_telegram_brief(
            title="War Room Morning Brief",
            as_of=calc.as_of,
            calc=calc,
            open_cases=open_cases,
            cov_rows=cov_rows,
            base_url="https://desk.npp.org.gh",
        )

        self.assertIn("<b>NPP SOCIAL LISTENING DESK · WAR ROOM MORNING BRIEF</b>", html)
        self.assertIn("TOP RISING TOPICS", html)
        self.assertIn("https://desk.npp.org.gh/trends/electricity-tariff/", html)
        self.assertIn("https://desk.npp.org.gh/issues/ISS-0409/", html)
        self.assertIn("🟢 <b>News feeds</b>", html)

    @override_settings(DESK_SAMPLE_MODE=False)  # live commands refuse to run in sample mode
    @patch("desk.notifications.send_telegram_message")
    def test_brief_shift_telegram_dispatch(self, mock_send):
        mock_send.return_value = (True, "98765", "")
        out = io.StringIO()

        env = {
            "TELEGRAM_BOT_TOKEN": "bot_token_abc",
            "TELEGRAM_CHAT_ID": "-1001234567890",
            "DESK_BASE_URL": "https://desk.npp.org.gh",
        }
        with patch.dict(os.environ, env):
            call_command("brief_shift", telegram=True, stdout=out)

        output = out.getvalue()
        self.assertIn("Shift brief dispatched to Telegram (#98765)", output)
        self.assertTrue(mock_send.called)

        # Verify arguments sent to send_telegram_message
        tg_text = mock_send.call_args[0][0]
        self.assertIn("<b>NPP SOCIAL LISTENING DESK · SHIFT INTELLIGENCE BRIEF</b>", tg_text)
        self.assertIn("https://desk.npp.org.gh/issues/", tg_text)

    @override_settings(DESK_SAMPLE_MODE=False)  # live commands refuse to run in sample mode
    def test_brief_shift_telegram_unconfigured_credentials_reports_warning(self):
        out = io.StringIO()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            call_command("brief_shift", telegram=True, stdout=out)

        output = out.getvalue()
        self.assertIn("Telegram dispatch skipped: credentials not configured.", output)

