"""Test settings for MedBook.

Extends base.py with configurable database and fast password hashing.
- Local: SQLite in-memory + DisableMigrations (fast)
- CI: PostgreSQL via DATABASE_URL env var (production-faithful)
"""

import os

import dj_database_url

from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database — configurable via DATABASE_URL env var
# ---------------------------------------------------------------------------
# Local: SQLite in-memory. CI: PostgreSQL (set DATABASE_URL in workflow).
DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///:memory:",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Disable migrations — only with SQLite (local speed optimization)
# ---------------------------------------------------------------------------
# En CI con PostgreSQL queremos que las migraciones corran realmente.
_engine = DATABASES["default"]["ENGINE"]
if "sqlite" in os.path.basename(_engine):

    class DisableMigrations:
        """Mocks the migration module to prevent Django from running migrations."""

        def __contains__(self, item: str) -> bool:
            return True

        def __getitem__(self, item: str) -> None:
            return None

    MIGRATION_MODULES = DisableMigrations()

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
