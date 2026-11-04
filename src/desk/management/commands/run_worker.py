import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Simple pilot worker: read the news feeds every --collect-every seconds and recalculate trends "
            "every --recompute-every seconds. Stop with Ctrl+C. A scheduler (cron, launchd, systemd) can run "
            "collect_news and recompute_trends instead.")

    def add_arguments(self, parser):
        parser.add_argument("--collect-every", type=int, default=300)
        parser.add_argument("--recompute-every", type=int, default=60)
        parser.add_argument("--once", action="store_true", help="Run one collection and one recalculation, then exit.")

    def handle(self, *args, **options):
        last_collect = None
        try:
            while True:
                started = time.monotonic()
                if last_collect is None or started - last_collect >= options["collect_every"]:
                    call_command("collect_news", stdout=self.stdout, stderr=self.stderr)
                    call_command("collect_social", stdout=self.stdout, stderr=self.stderr)
                    last_collect = started
                call_command("recompute_trends", alerts=True, stdout=self.stdout, stderr=self.stderr)
                if options["once"]:
                    return
                time.sleep(max(1, options["recompute_every"] - (time.monotonic() - started)))
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")
