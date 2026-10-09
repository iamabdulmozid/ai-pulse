"""Django settings for AI Pulse (Phase 0).

Stack is fixed (see docs/tech/architecture.md). Configuration is read from the environment via
django-environ. The production database is PostgreSQL 16 (set DATABASE_URL in docker-compose); local
development/tests fall back to SQLite so the suite runs without a DB server.
"""
from datetime import date
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "dev-insecure-key-change-me"),
    ALLOWED_HOSTS=(list, ["*"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    DEMO_TODAY=(str, "2026-10-15"),
    OPENAI_API_KEY=(str, ""),
    OPENAI_MODEL=(str, "gpt-4o-mini"),
    CHROMA_HOST=(str, "localhost"),
    CHROMA_PORT=(int, 8000),
    ASSISTANT_FALLBACK_MODE=(bool, False),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
# Read .env if present (local dev); in containers the environment is passed directly.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# --- Demo clock -------------------------------------------------------------
# DEMO_TODAY is the load-bearing "today" for the engine and the seed (docs/ai/prediction-engine.md).
DEMO_TODAY = date.fromisoformat(env("DEMO_TODAY"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_q",
    # AI Pulse apps
    "apps.accounts",
    "apps.masterdata",
    "apps.orders",
    "apps.factories",
    "apps.production",
    "apps.predictions",
    "apps.alerts",
    "apps.reports",
    "apps.assistant",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "karbar_pulse.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.dashboard.context_processors.shell",
            ],
        },
    },
]

WSGI_APPLICATION = "karbar_pulse.wsgi.application"
ASGI_APPLICATION = "karbar_pulse.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Manifest/compression is enabled in production (after collectstatic). Dev/tests use plain storage so
# templates render without a staticfiles manifest.
_staticfiles_backend = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if env.bool("MANIFEST_STATIC", default=False)
    else "django.contrib.staticfiles.storage.StaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": _staticfiles_backend},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:overview"
LOGOUT_REDIRECT_URL = "accounts:login"

# Uploads (docs/tech/security.md)
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "media/"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per file
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES

# django-q2 — Postgres ORM broker, no Redis (docs/tech/architecture.md)
Q_CLUSTER = {
    "name": "karbar_pulse",
    "workers": 2,
    "timeout": 600,
    "retry": 1200,
    "orm": "default",
    "catch_up": False,
}

# OpenAI / assistant
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL")
CHROMA_HOST = env("CHROMA_HOST")
CHROMA_PORT = env("CHROMA_PORT")
ASSISTANT_FALLBACK_MODE = env("ASSISTANT_FALLBACK_MODE")

# Sample data (for seed_demo + answer-key parity tests)
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

# Security (hardened when DEBUG is off; see docs/tech/security.md)
if not DEBUG:
    # Behind nginx (and Cloudflare): trust the forwarded proto so request.is_secure() is correct.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 2592000
    X_FRAME_OPTIONS = "DENY"
