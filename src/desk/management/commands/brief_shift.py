"""Generate shift brief and handover reports (05:45 GMT morning brief, 21:30 handover).

Summarizes:
1. Top rising political and policy trends with mention deltas.
2. Open critical issues needing attention or editor decision.
3. Source coverage health, delayed feeds, and capped platforms.
4. Next actions and shift handover notes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from desk import coverage, trends
from desk.models import Case


class Command(BaseCommand):
    help = "Generate a shift briefing report (05:45 morning brief or 21:30 evening handover)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            default="Shift Intelligence Brief",
            help="Custom header for the briefing report.",
        )
        parser.add_argument(
            "--telegram",
            action="store_true",
            help="Also dispatch the summary to the Telegram War Room channel.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        calc = trends.latest()
        as_of = calc.as_of if calc else now

        lines = [
            f"🇬🇭 NPP SOCIAL LISTENING DESK · {options['title'].upper()}",
            f"Generated: {as_of.strftime('%d %b %Y · %H:%M')} GMT",
            "=" * 60,
            "",
            "1. TOP RISING TOPICS & MOMENTUM (60-min window)",
        ]

        if calc and calc.rows.filter(rank__isnull=False).exists():
            for row in calc.rows.filter(rank__isnull=False).order_by("rank")[:5]:
                new_flag = " [NEW]" if row.is_new else ""
                delta = f"+{row.change}" if row.change > 0 else str(row.change)
                lines.append(
                    f"  #{row.rank} {row.topic.name}{new_flag}: {row.current_count} mentions ({delta}) · {row.observed_label}"
                )
        else:
            lines.append("  No topics currently above the 5-mention threshold.")

        lines.extend([
            "",
            "2. CRITICAL ISSUES & QUEUE",
        ])

        open_cases = Case.objects.exclude(status=Case.Status.CLOSED).order_by("due_at")
        if open_cases.exists():
            for c in open_cases:
                owner = c.owner.get_full_name() if c.owner else "Unassigned"
                due = c.due_at.strftime("%H:%M GMT")
                urgency = c.get_urgency_display()
                lines.append(f"  • [{c.ref}] {c.claim[:80]}...")
                lines.append(f"    Urgency: {urgency} | Status: {c.get_status_display()} | Owner: {owner} | Due: {due}")
                lines.append(f"    Next: {c.next_action}")
        else:
            lines.append("  No active cases in queue.")

        lines.extend([
            "",
            "3. SOURCE COVERAGE & PLATFORM HEALTH",
        ])

        cov = coverage.coverage(as_of)
        for row in cov.get("rows", []):
            status = row.get("status", "").upper()
            check = row.get("check", "")
            lines.append(f"  • {row.get('name')}: [{status}] - {check}")

        report_text = "\n".join(lines)
        self.stdout.write(report_text)

        if options["telegram"]:
            from desk import notifications
            token, chat_id, _ = notifications.get_telegram_config()
            if not token or not chat_id:
                self.stdout.write(self.style.WARNING("Telegram dispatch skipped: credentials not configured."))
            else:
                success, msg_id, err = notifications.send_telegram_message(
                    f"<pre>{report_text}</pre>", token, chat_id, parse_mode="HTML"
                )
                if success:
                    self.stdout.write(self.style.SUCCESS(f"Shift brief dispatched to Telegram (# {msg_id})."))
                else:
                    self.stdout.write(self.style.ERROR(f"Telegram dispatch failed: {err}"))

