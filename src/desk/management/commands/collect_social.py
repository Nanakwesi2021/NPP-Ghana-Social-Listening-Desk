"""Read configured social media sources (X, YouTube) once and store new items.

Handles credentials strictly through environment variables. If X_BEARER_TOKEN is not
configured, the X source remains in an awaiting state without throwing unhandled errors.
"""
from django.core.management.base import BaseCommand

from desk.collectors import x as x_collector, youtube as youtube_collector
from desk.ingest import ensure_groups


class Command(BaseCommand):
    help = "Read configured social media sources (X, YouTube) once and store new items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-sources",
            action="store_true",
            help="Ensure social sources (X, YouTube) exist in the database.",
        )

    def handle(self, *args, **options):
        ensure_groups()
        x_source = x_collector.ensure_x_source(sync=options["sync_sources"])
        yt_source = youtube_collector.ensure_youtube_source(sync=options["sync_sources"])

        # 1. Collect X (Recent Search)
        if not x_collector.get_bearer_token():
            self.stdout.write(f"{x_source.name}: not collected · awaiting X_BEARER_TOKEN in environment.")
        else:
            r = x_collector.collect_x(x_source)
            if r.result == "failed":
                self.stdout.write(self.style.WARNING(f"{x_source.name}: failed · {r.note}"))
            elif r.result == "capped":
                self.stdout.write(self.style.NOTICE(f"{x_source.name}: capped ({r.new_items} new of {r.seen}) · {r.note}"))
            else:
                tags = ", ".join(f"{k} {v}" for k, v in sorted(r.tagged.items())) or "none"
                self.stdout.write(self.style.SUCCESS(f"{x_source.name}: {r.new_items} new of {r.seen} posts · tagged: {tags}"))

        # 2. Collect YouTube (Public broadcast channels)
        r_yt = youtube_collector.collect_youtube(yt_source)
        if r_yt.result == "failed":
            self.stdout.write(self.style.WARNING(f"{yt_source.name}: failed · {r_yt.note}"))
        else:
            tags = ", ".join(f"{k} {v}" for k, v in sorted(r_yt.tagged.items())) or "none"
            self.stdout.write(self.style.SUCCESS(f"{yt_source.name}: {r_yt.new_items} new of {r_yt.seen} videos · tagged: {tags}"))

