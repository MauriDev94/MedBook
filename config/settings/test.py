"""Test settings for MedBook.

Extends base.py with production-faithful PostgreSQL testing.

Official test runs MUST use PostgreSQL, locally and in CI. Do not fall back to
SQLite here: SQLite can hide migration/schema issues that PostgreSQL catches.
"""

import dj_database_url

from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database — PostgreSQL by default
# ---------------------------------------------------------------------------
# Local and CI should use the same database engine to avoid false-green tests.
# Override DATABASE_URL when your local credentials differ.
DATABASES = {
    "default": dj_database_url.config(
        default="postgres://postgres:postgres@localhost:5436/medbook_test",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Faster password hashing
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------------------------------------------------------------------------
# Email backend
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
