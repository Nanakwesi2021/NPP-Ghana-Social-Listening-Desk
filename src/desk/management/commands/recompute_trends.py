from datetime import datetime

from django.core.management.base import BaseCommand

from desk import clock, trends


class Command(BaseCommand):
    help = "Recalculate the trend windows ending now (or at --as-of) and store them."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", help="ISO time to calculate for, e.g. 2026-11-03T10:37:00Z. Default: now.")
        parser.add_argument("--prune-days", type=int, default=7, help="Prune calculations older than N days (default 7).")

    def handle(self, *args, **options):
        as_of = datetime.fromisoformat(options["as_of"].replace("Z", "+00:00")) if options["as_of"] else clock.now()
        calc = trends.compute(as_of)
        if options["prune_days"]:
            pruned = trends.prune(days=options["prune_days"], as_of=as_of)
            if pruned:
                self.stdout.write(f"Pruned {pruned} old calculation(s).")
        ranked = calc.rows.filter(rank__isnull=False).order_by("rank").select_related("topic")
        self.stdout.write(self.style.SUCCESS(f"Windows ending {calc.as_of:%H:%M} GMT: {ranked.count()} ranked topics."))
        for row in ranked[:5]:
            self.stdout.write(f"  {row.rank}. {row.topic.name}: {row.current_count} vs {row.previous_count} ({row.observed_label})")
