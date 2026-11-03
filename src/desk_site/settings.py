"""Settings for the Social Listening Desk.

Sample mode replays the fictional "Sample shift" from tests/fixtures/sample_shift and
enables the role switcher. Turn it off with DESK_SAMPLE_MODE=0 before any shared pilot.
"""
import os
import urllib.parse
from pathlib import Path

from desk_site.safety import check_database_url, sample_mode

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# Read .env file from repository root if present
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
    SECRET_KEY = "local-development-only-not-secret"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "desk",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "desk_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "desk.context_processors.desk",
            ],
        },
    },
]

WSGI_APPLICATION = "desk_site.wsgi.application"

_db_url = check_database_url(os.environ.get("DATABASE_URL", "").strip())
if _db_url:
    _parsed = urllib.parse.urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username or "",
            "PASSWORD": _parsed.password or "",
            "HOST": _parsed.hostname or "",
            "PORT": _parsed.port or 5432,
            "CONN_MAX_AGE": 600,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DESK_DATABASE", str(REPO_ROOT / "data" / "desk.sqlite3")),
            "OPTIONS": {
                "timeout": 20,
            },
        }
    }

TEST_RUNNER = "desk_site.test_runner.FastPasswordTestRunner"

# Backups (desk/backups.py, manage.py backup_desk). Copy this folder off the server too.
DESK_BACKUP_DIR = Path(os.environ.get("DESK_BACKUP_DIR", str(REPO_ROOT / "backups")))

# /healthz/ (desk/health.py): a live desk is unhealthy when trends or collection are older than these.
DESK_HEALTH_MAX_TREND_AGE_MINUTES = int(os.environ.get("DESK_HEALTH_MAX_TREND_AGE_MINUTES", "5"))
DESK_HEALTH_MAX_POLL_AGE_MINUTES = int(os.environ.get("DESK_HEALTH_MAX_POLL_AGE_MINUTES", "20"))

# Sign-in protection (desk/signin.py)
DESK_SIGNIN_MAX_FAILURES = int(os.environ.get("DESK_SIGNIN_MAX_FAILURES", "5"))
DESK_SIGNIN_MAX_FAILURES_PER_IP = int(os.environ.get("DESK_SIGNIN_MAX_FAILURES_PER_IP", "20"))
DESK_SIGNIN_LOCK_MINUTES = int(os.environ.get("DESK_SIGNIN_LOCK_MINUTES", "15"))

# Behind Nginx (deploy/nginx.conf), trust its X-Real-IP and X-Forwarded-Proto headers.
# Without this, HTTPS redirects loop forever and every visitor appears to come from one address.
# Leave off when the app is reachable directly, because anyone could then forge those headers.
DESK_TRUST_PROXY_HEADERS = os.environ.get("DESK_TRUST_PROXY_HEADERS", "0") == "1"
if DESK_TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"  # Ghana keeps GMT all year; every time on the desk is shown in GMT.
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "desk:overview"
LOGOUT_REDIRECT_URL = "login"

DESK_SAMPLE_MODE = sample_mode(os.environ.get("DESK_SAMPLE_MODE"), debug=DEBUG, database_url=_db_url,
                               allowed_hosts=ALLOWED_HOSTS)
DESK_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_shift"
DESK_WINDOW_MINUTES = 60
DESK_MIN_MENTIONS = 5
DESK_REFRESH_SECONDS = 60

# Production security hardening (when DJANGO_DEBUG=0)
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
