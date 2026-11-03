"""Start-up guard: the passwordless Sample shift sign-in must never run as a live deployment."""
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
