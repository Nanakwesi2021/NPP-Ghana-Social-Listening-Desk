"""Read configured social media sources (X, YouTube) once and store new items.

Handles credentials strictly through environment variables. If X_BEARER_TOKEN is not
configured, the X source remains in an awaiting state without throwing unhandled errors.
"""
from django.core.management.base import BaseCommand

from desk.collectors import x as x_collector, youtube as youtube_collector
from desk.ingest import ensure_groups
from desk.management.commands.submit_social_link import ensure_manual_source
from desk.models import Platform, Source
from desk_site.safety import refuse_in_sample_mode


def sync_all_social_sources():
    """Ensure all social platforms exist with their appropriate kind and metadata."""
    x_source = x_collector.ensure_x_source(sync=True)
    yt_source = youtube_collector.ensure_youtube_source(sync=True)
    ensure_manual_source(Platform.FACEBOOK)
    ensure_manual_source(Platform.TIKTOK)
    ensure_manual_source(Platform.WHATSAPP)
    Source.objects.get_or_create(
        key="instagram",
        defaults={
            "name": "Instagram",
            "group": "Instagram",
            "detail": "Public accounts",
            "platform": Platform.INSTAGRAM,
            "kind": Source.Kind.AWAITING,
            "method": "Awaiting approved access",
            "scope": "No collection yet. An outlet quoting an Instagram post counts as that outlet.",
            "position": 50,
        },
    )
    Source.objects.get_or_create(
        key="threads",
        defaults={
            "name": "Threads",
            "group": "Threads",
            "detail": "Public accounts",
            "platform": Platform.THREADS,
            "kind": Source.Kind.AWAITING,
            "method": "Awaiting approved access",
            "scope": "No collection yet.",
            "position": 60,
        },
    )
    return x_source, yt_source


class Command(BaseCommand):
    help = "Read configured social media sources (X, YouTube) once and store new items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-sources",
            action="store_true",
            help="Ensure all social sources (X, YouTube, Facebook, TikTok, WhatsApp, etc.) exist in the database.",
        )

    def handle(self, *args, **options):
        refuse_in_sample_mode("collect_social", "reads live YouTube and X feeds")
        ensure_groups()
        if options["sync_sources"]:
            x_source, yt_source = sync_all_social_sources()
            self.stdout.write(self.style.SUCCESS("Synced social sources: X, YouTube, Facebook, TikTok, WhatsApp, Instagram, Threads."))
        else:
            x_source = x_collector.ensure_x_source()
            yt_source = youtube_collector.ensure_youtube_source()

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
