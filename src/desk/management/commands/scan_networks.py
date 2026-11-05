"""Unified network scanning and breakout alert command.

Scans all configured networks (News Portals, YouTube broadcast feeds, X recent search,
and analyst-submitted manual links), recalculates cross-platform trend momentum,
and automatically pushes key trending breakouts and cross-network spikes out to
internal channels (Telegram War Room).
"""
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand

from desk import alerts, clock, trends
from desk.management.commands.collect_social import sync_all_social_sources
from desk_site.safety import refuse_in_sample_mode


class Command(BaseCommand):
    help = "Scan all monitored networks (news portals & social feeds), recompute trends, and push out breakouts."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", help="ISO time to compute trends for. Defaults to current time.")
        parser.add_argument("--no-news", action="store_true", help="Skip polling news portal feeds.")
        parser.add_argument("--no-social", action="store_true", help="Skip polling social feeds (YouTube, X).")
        parser.add_argument("--no-push", action="store_true", help="Detect breakouts without dispatching Telegram alerts.")
        parser.add_argument("--sync-sources", action="store_true", help="Ensure all platform sources exist in database.")
        parser.add_argument("--prune-days", type=int, default=7, help="Prune trend calculations older than N days.")

    def handle(self, *args, **options):
        refuse_in_sample_mode("scan_networks", "reads live feeds, calculates trends for now and can push alerts")
        if options["sync_sources"]:
            sync_all_social_sources()
            self.stdout.write(self.style.SUCCESS("Synced all monitored news and social platform sources."))

        # 1. Scan News Portals
        if not options["no_news"]:
            self.stdout.write("--- Scanning Ghanaian News Portals (Citi Newsroom, Joy Online, Daily Graphic) ---")
            call_command("collect_news", stdout=self.stdout, stderr=self.stderr)

        # 2. Scan Social Feeds (YouTube, X)
        if not options["no_social"]:
            self.stdout.write("--- Scanning Social Platforms (YouTube broadcast feeds, X) ---")
            call_command("collect_social", stdout=self.stdout, stderr=self.stderr)

        # 3. Recalculate Trends across all networks
        as_of = datetime.fromisoformat(options["as_of"].replace("Z", "+00:00")) if options["as_of"] else clock.now()
        self.stdout.write(f"--- Recalculating 60-minute Trend Windows ending {as_of:%H:%M} GMT ---")
        calc = trends.compute(as_of)
        if options["prune_days"]:
            pruned = trends.prune(days=options["prune_days"], as_of=as_of)
            if pruned:
                self.stdout.write(f"Pruned {pruned} old calculation(s).")

        ranked = calc.rows.filter(rank__isnull=False).order_by("rank").select_related("topic")
        self.stdout.write(self.style.SUCCESS(f"Ranked {ranked.count()} active topic(s):"))
        for row in ranked[:5]:
            self.stdout.write(f"  #{row.rank} {row.topic.name}: {row.current_count} mentions (+{row.change}) [{row.observed_label}]")

        # 4. Detect and Push Out Breakout Issues
        self.stdout.write("--- Cross-Network Spike & Breakout Detection ---")
        if options["no_push"]:
            self.stdout.write("Alert dispatch skipped (--no-push active).")
            for row in ranked:
                is_breakout, alert_type, tier = alerts.classify_breakout(row)
                if is_breakout:
                    self.stdout.write(f"  [DETECTED] {alert_type}: {row.topic.name} (+{row.change}, {len(row.platforms)} platforms)")
        else:
            dispatched = alerts.detect_and_dispatch_trend_alerts(calc)
            if not dispatched:
                self.stdout.write("No topics currently meet cross-network breakout or velocity surge criteria.")
            else:
                for alert in dispatched:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [PUSHED] {alert.get_alert_type_display()} · {alert.topic.name} · "
                            f"{alert.current_count} mentions (+{alert.change}) · Status: {alert.get_status_display()}"
                        )
                    )

