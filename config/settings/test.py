"""Test settings for MedBook.

Extends base.py with SQLite in-memory, no migrations, and fast password hashing.
"""
from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database — SQLite in-memory for test speed
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ---------------------------------------------------------------------------
# Disable migrations for speed
# ---------------------------------------------------------------------------
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
