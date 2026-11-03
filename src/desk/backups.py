"""Database backups with a restore check.

SQLite is copied with SQLite's online backup API, so a running desk can be backed up safely.
PostgreSQL is dumped with pg_dump in its custom format. Every backup is read back before it
is kept: SQLite must pass PRAGMA integrity_check, and pg_restore must be able to list the
dump. Files are written readable by their owner only, because they hold personal data.

Backups on the same server do not survive losing that server. Copy them off-site
(object storage at the hosting provider) as part of the deployment.
"""
import gzip
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.db import connection

NAME_PATTERN = re.compile(r"^desk-(sqlite|postgres)-\d{8}T\d{6}Z\.(sqlite3\.gz|dump)$")


class BackupError(Exception):
    pass


def _stamp(now):
    return now.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _private(path):
    os.chmod(path, 0o600)


def verify_sqlite(path):
    """Decompress to a temporary file and run SQLite's integrity check on it."""
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "check.sqlite3"
        try:
            with gzip.open(path, "rb") as src, open(plain, "wb") as dst:
                shutil.copyfileobj(src, dst)
        except (OSError, EOFError) as exc:
            raise BackupError(f"Cannot read {Path(path).name}: {exc}") from exc
        try:
            con = sqlite3.connect(plain)
            try:
                status = con.execute("PRAGMA integrity_check").fetchone()[0]
                tables = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            finally:
                con.close()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"{Path(path).name} is not a readable SQLite database: {exc}") from exc
    if status != "ok" or tables == 0:
        raise BackupError(f"{Path(path).name} failed the integrity check ({status}, {tables} tables)")
    return tables


def _give_up_after(seconds):
    """Progress callback for sqlite3.backup. Python retries a busy database forever; this stops it."""
    deadline = time.monotonic() + seconds

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise BackupError(f"The database stayed busy for {seconds} seconds; backup abandoned. Try again.")
    return progress


def backup_sqlite(dest_dir, now, busy_timeout=120):
    final = Path(dest_dir) / f"desk-sqlite-{_stamp(now)}.sqlite3.gz"
    connection.ensure_connection()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.sqlite3"
        target = sqlite3.connect(copy)
        try:
            connection.connection.backup(target, pages=256, progress=_give_up_after(busy_timeout), sleep=0.1)
        finally:
            target.close()
        partial = final.with_suffix(final.suffix + ".partial")
        with open(copy, "rb") as src, gzip.open(partial, "wb") as dst:
            shutil.copyfileobj(src, dst)
    _private(partial)
    verify_sqlite(partial)
    partial.rename(final)
    return final


def pg_env_and_args(db):
    env = {**os.environ, "PGPASSWORD": db.get("PASSWORD") or ""}
    args = ["--host", db.get("HOST") or "localhost", "--port", str(db.get("PORT") or 5432),
            "--username", db.get("USER") or "", db["NAME"]]
    return env, args


def verify_postgres(path):
    try:
        listing = subprocess.run(["pg_restore", "--list", str(path)], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise BackupError("pg_restore is not installed; install the PostgreSQL client tools") from exc
    if listing.returncode != 0 or "TABLE" not in listing.stdout:
        raise BackupError(f"{Path(path).name} could not be listed by pg_restore: {listing.stderr.strip()[:200]}")
    return sum(1 for line in listing.stdout.splitlines() if " TABLE " in line)


def backup_postgres(dest_dir, now):
    final = Path(dest_dir) / f"desk-postgres-{_stamp(now)}.dump"
    partial = final.with_suffix(".dump.partial")
    env, args = pg_env_and_args(connection.settings_dict)
    try:
        result = subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(partial), *args],
                                env=env, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise BackupError("pg_dump is not installed; install the PostgreSQL client tools") from exc
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        raise BackupError(f"pg_dump failed: {result.stderr.strip()[:300]}")
    _private(partial)
    verify_postgres(partial)
    partial.rename(final)
    return final


def make_backup(dest_dir, now=None):
    now = now or datetime.now(dt_timezone.utc)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    if connection.vendor == "postgresql":
        return backup_postgres(dest, now)
    if connection.vendor == "sqlite":
        return backup_sqlite(dest, now)
    raise BackupError(f"Unsupported database: {connection.vendor}")


def verify(path):
    name = Path(path).name
    if name.endswith(".sqlite3.gz"):
        return verify_sqlite(path)
    if name.endswith(".dump"):
        return verify_postgres(path)
    raise BackupError(f"Not a desk backup: {name}")


def prune(dest_dir, keep_days, now=None):
    """Delete this command's own backups older than keep_days. Other files are never touched."""
    now = now or datetime.now(dt_timezone.utc)
    cutoff = now - timedelta(days=keep_days)
    removed = []
    for path in Path(dest_dir).iterdir():
        match = NAME_PATTERN.match(path.name)
        if not match:
            continue
        stamp = datetime.strptime(path.name.split("-")[2].split(".")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt_timezone.utc)
        if stamp < cutoff:
            path.unlink()
            removed.append(path.name)
    return removed
