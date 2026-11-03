from django.conf import settings
from django.core.management.base import BaseCommand

from desk.ingest import replay
from desk.models import ShiftClock


class Command(BaseCommand):
    help = "Replay the fictional Sample shift (news feed + social posts) into the local database."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true",
                            help="Delete sources, items, trends and cases first, discarding demo decisions.")
        parser.add_argument("--reset-clock", action="store_true",
                            help="Restart the shift clock at the sample time (10:37 GMT), keeping decisions.")

    def handle(self, *args, **options):
        if options["reset_clock"]:
            ShiftClock.objects.all().delete()
        stats = replay(settings.DESK_FIXTURE_DIR, wipe=options["wipe"])
        self.stdout.write(self.style.SUCCESS(
            f"Sample shift as of {stats['as_of']:%H:%M} GMT: {stats['items_new']} new items, "
            f"{stats['items_repeated']} repeated entries skipped, {stats['cases_new']} new cases, "
            f"{stats['ranked']} ranked topics."
        ))
