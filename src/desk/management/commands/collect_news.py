from django.core.management.base import BaseCommand

from desk.collectors import rss
from desk.ingest import ensure_groups


class Command(BaseCommand):
    help = "Read the configured news feeds once and store new items. A failing feed does not stop the others."

    def add_arguments(self, parser):
        parser.add_argument("--sync-sources", action="store_true",
                            help="Copy feed addresses, kinds, methods and notes from live_config.json onto existing outlets.")
        parser.add_argument("--retag", action="store_true",
                            help="Re-apply the current topic keyword rules to stored items from these feeds first.")

    def handle(self, *args, **options):
        ensure_groups()
        rss.ensure_topics()
        sources = rss.ensure_sources(sync=options["sync_sources"])
        if options["retag"]:
            self.stdout.write(f"Retagged: {rss.retag(sources)} items changed topics.")
        for source in sources:
            if source.kind != "collected" or not source.feed_url:
                self.stdout.write(f"{source.name}: not collected · {source.method}")
        for r in rss.collect(sources):
            if r.result == "failed":
                self.stdout.write(self.style.WARNING(f"{r.source.name}: failed · {r.note}"))
            else:
                tags = ", ".join(f"{k} {v}" for k, v in sorted(r.tagged.items())) or "none"
                self.stdout.write(self.style.SUCCESS(
                    f"{r.source.name}: {r.new_items} new of {r.seen} in feed · tagged: {tags}{' · ' + r.note if r.note else ''}"))
