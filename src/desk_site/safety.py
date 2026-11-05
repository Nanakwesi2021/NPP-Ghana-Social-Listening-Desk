"""Guards that keep the fictional Sample shift and a live desk apart.

The passwordless Sample shift sign-in must never run as a live deployment, and live
collection commands must never write into the Sample shift database.
"""
from django.core.exceptions import ImproperlyConfigured

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", ""}


POSTGRES_SCHEMES = ("postgres://", "postgresql://")


def check_database_url(database_url):
    """A DATABASE_URL that is set must be a PostgreSQL address.

    Anything else used to be ignored silently, so commands meant for the live database ran
    against the SQLite demo database instead. The value is never echoed: it holds a password.
    """
    if database_url and not database_url.startswith(POSTGRES_SCHEMES):
        raise ImproperlyConfigured(
            "DATABASE_URL is set but is not a PostgreSQL address (it must start with postgresql://). "
            "Refusing to fall back to the SQLite demo database. Fix DATABASE_URL, or unset it to use SQLite."
        )
    return database_url


def live_deployment_signals(*, debug, database_url, allowed_hosts):
    """Reasons to believe these settings describe a live deployment rather than a laptop demo."""
    signals = []
    if not debug:
        signals.append("DJANGO_DEBUG=0")
    if database_url:
        signals.append("DATABASE_URL is set")
    public = [h.strip() for h in allowed_hosts if h.strip() not in LOCAL_HOSTS]
    if public:
        signals.append("DJANGO_ALLOWED_HOSTS includes " + ", ".join(public))
    return signals


def refuse_in_sample_mode(command, does):
    """Stop a command that reads live sources or writes live trend data while sample mode is on.

    In sample mode the database is the fictional Sample shift. A live collection or trend
    calculation there mixes real items into the demo and puts a newer calculation ahead of its 10:37 one.
    command is how the person ran it (e.g. "collect_news"); does says what it would do.
    Call it first in handle(), before anything touches the database or the network.
    """
    from django.conf import settings
    from django.core.management.base import CommandError

    if not settings.DESK_SAMPLE_MODE:
        return
    # Sample mode never runs with DATABASE_URL set (see sample_mode below), so this is a SQLite path, not a secret.
    database = settings.DATABASES["default"]["NAME"]
    raise CommandError(
        f"{command} {does}, but sample mode is on: this database ({database}) is the fictional Sample shift. "
        "Refusing, so real and sample data never mix.\n"
        "Run it against the live desk instead, from src/:\n"
        f"  DESK_DATABASE=../data/live.sqlite3 DESK_SAMPLE_MODE=0 ../.venv/bin/python manage.py {command}\n"
        "or set DATABASE_URL to the PostgreSQL desk in that terminal. "
        "To reload the Sample shift itself, use replay_sample."
    )


def sample_mode(requested, **deployment):
    """Resolve DESK_SAMPLE_MODE.

    requested is the raw DESK_SAMPLE_MODE value ("1", "0" or None when unset). Unset means
    on only for a plain local demo. Asking for it on a live deployment stops the start-up.
    """
    signals = live_deployment_signals(**deployment)
    if requested is None:
        return not signals
    if requested.strip() != "1":
        return False
    if signals:
        raise ImproperlyConfigured(
            "DESK_SAMPLE_MODE=1 turns on the passwordless demo sign-in and cannot run on a live "
            f"deployment ({'; '.join(signals)}). Set DESK_SAMPLE_MODE=0."
        )
    return True
