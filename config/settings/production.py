"""Production settings for MedBook.

Extends base.py. All secrets and environment-specific values must come
from environment variables — never hardcoded here.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.production
"""

import dj_database_url
from decouple import Csv, config

from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must be set in production.")

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Proxy-aware client IP resolution (DRF throttling)
# ---------------------------------------------------------------------------
# Render sits its app behind a single edge layer (Cloudflare + Render's load
# balancer act as one hop from the app's perspective): the request reaching
# Gunicorn carries X-Forwarded-For with exactly one trusted hop prepended.
# DRF's SimpleRateThrottle.get_ident() uses REST_FRAMEWORK["NUM_PROXIES"] to
# pick "the Nth-from-last" IP in X-Forwarded-For instead of trusting
# REMOTE_ADDR (which would be the proxy's IP, not the real client's).
# Without this, every request behind Render's proxy collapses onto the same
# throttle bucket (the proxy IP), making per-client rate limiting useless.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "NUM_PROXIES": 1,
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ---------------------------------------------------------------------------
# Static files — WhiteNoise serves them directly from Gunicorn
# ---------------------------------------------------------------------------
MIDDLEWARE = [  # noqa: F405
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # right after SecurityMiddleware
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STATIC_URL = "/static/"

# ---------------------------------------------------------------------------
# CORS — portfolio API, no frontend to restrict
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True

STORAGES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Error tracking (Sentry) — gated by SENTRY_DSN
# ---------------------------------------------------------------------------
# Only initializes when SENTRY_DSN is set. Without it, this is a no-op:
# local dev and CI never need a DSN and must keep working unmodified.
# Never hardcode a DSN here — it always comes from the environment.
SENTRY_DSN = config("SENTRY_DSN", default="")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.0, cast=float),
        send_default_pii=False,
        environment=config("SENTRY_ENVIRONMENT", default="production"),
    )
