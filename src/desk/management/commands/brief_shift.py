"""Generate shift brief and handover reports (05:45 GMT morning brief, 21:30 handover).

Summarizes:
1. Top rising political and policy trends with mention deltas.
2. Open critical issues needing attention or editor decision.
3. Source coverage health, delayed feeds, and capped platforms.
4. Next actions and shift handover notes.
"""
import html
from django.core.management.base import BaseCommand
from django.utils import timezone

from desk import coverage, trends
from desk.models import Case


def format_telegram_brief(title, as_of, calc, open_cases, cov_rows, base_url):
    """Format structured HTML briefing message for Telegram War Room dispatch."""
    base_url = (base_url or "http://127.0.0.1:8000").rstrip("/")
    lines = [
        f"🇬🇭 <b>NPP SOCIAL LISTENING DESK · {html.escape(title.upper())}</b>",
        f"<i>Generated: {as_of.strftime('%d %b %Y · %H:%M')} GMT</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "🔥 <b>TOP RISING TOPICS (60-MIN WINDOW)</b>",
    ]
    if calc and calc.rows.filter(rank__isnull=False).exists():
        for row in calc.rows.filter(rank__isnull=False).order_by("rank")[:5]:
            new_flag = " <b>[NEW]</b>" if row.is_new else ""
            delta = f"+{row.change}" if row.change > 0 else str(row.change)
            topic_url = f"{base_url}/trends/{row.topic.slug}/"
            lines.append(
                f"• <a href=\"{topic_url}\"><b>#{row.rank} {html.escape(row.topic.name)}</b></a>{new_flag}: "
                f"{row.current_count} mentions (<b>{delta}</b>) · <i>{html.escape(row.observed_label)}</i>"
            )
    else:
        lines.append("• <i>No topics currently above the 5-mention threshold.</i>")

    lines.extend([
        "",
        "🚨 <b>CRITICAL ISSUES & QUEUE</b>",
    ])
    if open_cases:
        for c in open_cases[:5]:
            owner = c.owner.get_full_name() if c.owner else "Unassigned"
            due = c.due_at.strftime("%H:%M GMT")
            urgency = c.get_urgency_display()
            case_url = f"{base_url}/issues/{c.ref}/"
            claim_snippet = html.escape(c.claim[:80]) + "..." if len(c.claim) > 80 else html.escape(c.claim)
            lines.append(f"• <a href=\"{case_url}\"><b>[{c.ref}]</b></a> “{claim_snippet}”")
            lines.append(f"  <b>Urgency:</b> {urgency} | <b>Due:</b> {due} | <b>Owner:</b> {html.escape(owner)}")
            lines.append(f"  <b>Next:</b> <i>{html.escape(c.next_action)}</i>")
    else:
        lines.append("• <i>No active cases in queue.</i>")

    lines.extend([
        "",
        "📡 <b>SOURCE COVERAGE & PLATFORM HEALTH</b>",
    ])
    status_icons = {
        "current": "🟢",
        "delayed": "🟡",
        "unavailable": "🔴",
        "manual": "🔵",
        "awaiting": "⚪",
        "tips": "💬",
    }
    for row in cov_rows:
        st = row.get("status", "").lower()
        icon = status_icons.get(st, "•")
        lines.append(
            f"{icon} <b>{html.escape(row.get('name', ''))}</b>: [{row.get('label', '').upper()}] - {html.escape(row.get('check', ''))}"
        )

    return "\n".join(lines)


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

        open_cases = list(Case.objects.exclude(status=Case.Status.CLOSED).order_by("due_at"))
        if open_cases:
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
        cov_rows = cov.get("rows", [])
        for row in cov_rows:
            status = row.get("status", "").upper()
            check = row.get("check", "")
            lines.append(f"  • {row.get('name')}: [{status}] - {check}")

        report_text = "\n".join(lines)
        self.stdout.write(report_text)

        if options["telegram"]:
            from desk import notifications
            token, chat_id, base_url = notifications.get_telegram_config()
            if not token or not chat_id:
                self.stdout.write(self.style.WARNING("Telegram dispatch skipped: credentials not configured."))
            else:
                tg_message = format_telegram_brief(
                    options["title"], as_of, calc, open_cases, cov_rows, base_url
                )
                success, msg_id, err = notifications.send_telegram_message(
                    tg_message, token, chat_id, parse_mode="HTML"
                )
                if success:
                    self.stdout.write(self.style.SUCCESS(f"Shift brief dispatched to Telegram (#{msg_id})."))
                else:
                    self.stdout.write(self.style.ERROR(f"Telegram dispatch failed: {err}"))
