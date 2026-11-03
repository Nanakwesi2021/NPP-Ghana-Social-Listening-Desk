from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from desk import backups


class Command(BaseCommand):
    help = ("Back up the desk database (SQLite or PostgreSQL), check the backup can be read back, "
            "and delete this command's backups older than --keep-days.")

    def add_arguments(self, parser):
        parser.add_argument("--dest", default=str(settings.DESK_BACKUP_DIR),
                            help="Folder for backups (default: DESK_BACKUP_DIR).")
        parser.add_argument("--keep-days", type=int, default=14, help="Delete backups older than this. 0 keeps all.")
        parser.add_argument("--verify", metavar="FILE", help="Only check that an existing backup can be read back.")

    def handle(self, *args, **options):
        try:
            if options["verify"]:
                tables = backups.verify(options["verify"])
                self.stdout.write(self.style.SUCCESS(f"Backup is readable: {tables} tables."))
                return
            path = backups.make_backup(options["dest"])
            size_kb = path.stat().st_size // 1024
            self.stdout.write(self.style.SUCCESS(f"Backup written and verified: {path} ({size_kb} KB)."))
            if options["keep_days"] > 0:
                removed = backups.prune(options["dest"], options["keep_days"])
                if removed:
                    self.stdout.write(f"Deleted {len(removed)} backup(s) older than {options['keep_days']} days.")
        except backups.BackupError as exc:
            raise CommandError(str(exc)) from exc
