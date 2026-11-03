"""backup_desk (desk/backups.py), offline: SQLite for real, PostgreSQL with pg_dump stubbed."""
import gzip
import os
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from desk import backups
from desk.models import Topic


class BackupTests(TransactionTestCase):
    """TransactionTestCase: a backup must run outside a transaction, as it does in production."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in self.tmp.iterdir()] and None)
        Topic.objects.create(slug="dumsor", name="Dumsor")

    def test_sqlite_backup_is_private_compressed_and_verified(self):
        path = backups.make_backup(self.tmp, now=datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc))
        self.assertEqual(path.name, "desk-sqlite-20261103T020000Z.sqlite3.gz")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertGreater(backups.verify(path), 0)
        self.assertFalse(list(self.tmp.glob("*.partial")))

    def test_a_damaged_backup_fails_the_check(self):
        bad = self.tmp / "desk-sqlite-20261103T020000Z.sqlite3.gz"
        with gzip.open(bad, "wb") as fh:
            fh.write(b"not a database")
        with self.assertRaises(backups.BackupError):
            backups.verify(bad)
        with self.assertRaises(CommandError):
            call_command("backup_desk", verify=str(bad), stdout=StringIO())

    def test_prune_removes_only_old_desk_backups(self):
        for name in ("desk-sqlite-20261001T020000Z.sqlite3.gz", "desk-postgres-20261002T020000Z.dump",
                     "desk-sqlite-20261102T020000Z.sqlite3.gz", "notes.txt", "desk-sqlite-garbage.sqlite3.gz"):
            (self.tmp / name).write_bytes(b"x")
        removed = backups.prune(self.tmp, keep_days=14, now=datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual(sorted(removed), ["desk-postgres-20261002T020000Z.dump", "desk-sqlite-20261001T020000Z.sqlite3.gz"])
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()),
                         ["desk-sqlite-20261102T020000Z.sqlite3.gz", "desk-sqlite-garbage.sqlite3.gz", "notes.txt"])

    def test_command_writes_and_reports(self):
        out = StringIO()
        call_command("backup_desk", dest=str(self.tmp), keep_days=0, stdout=out)
        self.assertIn("Backup written and verified", out.getvalue())
        self.assertEqual(len(list(self.tmp.glob("desk-sqlite-*.sqlite3.gz"))), 1)

    def test_postgres_backup_runs_pg_dump_then_checks_it(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs.get("env", {}).get("PGPASSWORD")))
            if cmd[0] == "pg_dump":
                Path(cmd[cmd.index("--file") + 1]).write_bytes(b"PGDMP")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "1; 2615 2200 TABLE public desk_case npp\n", "")

        db = {"NAME": "npp_desk", "USER": "npp_user", "PASSWORD": "pw", "HOST": "localhost", "PORT": 5432}
        with mock.patch.object(backups.connection, "vendor", "postgresql"), \
                mock.patch.object(backups.connection, "settings_dict", db), \
                mock.patch("desk.backups.subprocess.run", side_effect=fake_run):
            path = backups.make_backup(self.tmp, now=datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc))
        self.assertEqual(path.name, "desk-postgres-20261103T020000Z.dump")
        self.assertEqual([c[0][0] for c in calls], ["pg_dump", "pg_restore"])
        self.assertEqual(calls[0][1], "pw")  # password passed in the environment, never on the command line
        self.assertNotIn("pw", " ".join(calls[0][0]))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_a_busy_database_gives_up_instead_of_hanging(self):
        progress = backups._give_up_after(0)
        with self.assertRaisesMessage(backups.BackupError, "stayed busy"):
            progress(5, 10, 10)  # status 5 = SQLITE_BUSY

    def test_failed_pg_dump_leaves_nothing_behind(self):
        db = {"NAME": "npp_desk", "USER": "u", "PASSWORD": "", "HOST": "localhost", "PORT": 5432}
        failing = subprocess.CompletedProcess(["pg_dump"], 1, "", "connection refused")
        with mock.patch.object(backups.connection, "vendor", "postgresql"), \
                mock.patch.object(backups.connection, "settings_dict", db), \
                mock.patch("desk.backups.subprocess.run", return_value=failing):
            with self.assertRaisesMessage(backups.BackupError, "pg_dump failed: connection refused"):
                backups.make_backup(self.tmp)
        self.assertEqual(list(self.tmp.iterdir()), [])
